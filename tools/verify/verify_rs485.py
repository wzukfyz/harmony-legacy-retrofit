#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Runs bounded end-to-end RS485, MQTT, alarm, and recovery checks.

The Modbus slave runs in a managed asyncio thread, so verification can change
registers without restarting processes or releasing the serial port per phase.

Usage: python tools/verify/verify_rs485.py [config.yaml] [--timeout 25]
"""

import argparse
import json
import queue
import socket
import sys
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt
import serial
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DEFAULT = PROJECT_ROOT / "tools" / "config.yaml"
MODBUS_SIM_DIR = PROJECT_ROOT / "tools" / "modbus_sim"
DEVICE_NAME = "普中演示从站 v1"

sys.path.insert(0, str(MODBUS_SIM_DIR))
from slave_rtu import build_context  # noqa: E402
from managed_server import ManagedModbusServer  # noqa: E402


class MqttProbe:
    """Collects report and alarm messages during bounded verification phases."""

    def __init__(self, broker, port, report_topic, alarm_topic):
        self.report_topic = report_topic
        self.alarm_topic = alarm_topic
        self.connected = threading.Event()
        self.messages = queue.Queue()
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="verify_rs485_{}".format(threading.get_ident()),
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect(broker, port, keepalive=15)
        self.client.loop_start()
        if not self.connected.wait(5):
            self.close()
            raise RuntimeError("MQTT Broker 连接超时")

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            return
        client.subscribe([(self.report_topic, 0), (self.alarm_topic, 0)])
        self.connected.set()

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return
        self.messages.put((message.topic, payload))

    def drain(self):
        """Discards messages left from a preceding verification phase."""
        while True:
            try:
                self.messages.get_nowait()
            except queue.Empty:
                return

    def close(self):
        self.client.disconnect()
        self.client.loop_stop()


def wait_for_points(probe, phase, topic, expected, timeout_s):
    """Waits for each expected point value until a phase deadline."""
    deadline = time.monotonic() + timeout_s
    matched = set()
    while len(matched) < len(expected):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            missing = sorted(set(expected) - matched)
            raise TimeoutError("{} 超时，未收到点位：{}".format(phase, ", ".join(missing)))
        try:
            received_topic, payload = probe.messages.get(timeout=min(remaining, 0.5))
        except queue.Empty:
            continue
        point = payload.get("point")
        if received_topic != topic or payload.get("device") != DEVICE_NAME:
            continue
        if point not in expected:
            continue
        raw, scale, alarm = expected[point]
        if (payload.get("raw"), payload.get("scale"), payload.get("alarm")) != (
            raw, scale, alarm
        ):
            continue
        matched.add(point)
        print("[{}] {}".format(phase, payload), flush=True)
    print("[PASS] {}".format(phase), flush=True)


def run_phase(probe, phase, topic, expected, timeout_s):
    """Checks one phase after clearing messages from the preceding phase."""
    probe.drain()
    started = time.monotonic()
    wait_for_points(probe, phase, topic, expected, timeout_s)
    print("[TIME] {} {:.1f}s".format(phase, time.monotonic() - started), flush=True)


def main():
    """Runs normal, alarm, and recovery checks with bounded waits and cleanup."""
    parser = argparse.ArgumentParser(description="有界 RS485/MQTT 闭环验收")
    parser.add_argument("config", nargs="?", default=str(CONFIG_DEFAULT))
    parser.add_argument(
        "--timeout", type=int, default=25, help="每阶段超时秒数，默认 25"
    )
    args = parser.parse_args()
    if args.timeout < 5:
        parser.error("--timeout 不能小于 5 秒")

    config_path = Path(args.config)
    with config_path.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    serial_config = config["serial"]
    mqtt_config = config["mqtt"]

    with socket.create_connection(
        (mqtt_config["broker"], mqtt_config.get("port", 1883)), timeout=3
    ):
        pass
    with serial.Serial(
        serial_config["port"],
        baudrate=serial_config["baudrate"],
        bytesize=8,
        parity=serial_config.get("parity", "N"),
        stopbits=serial_config.get("stopbits", 1),
        timeout=0.1,
    ):
        pass

    print("[READY] Broker 可达，{} 串口空闲。".format(serial_config["port"]), flush=True)
    probe = MqttProbe(
        mqtt_config["broker"],
        mqtt_config.get("port", 1883),
        mqtt_config["topic"],
        mqtt_config["alarm_topic"],
    )
    slave = None
    values = list(config.get("registers", {}).get("initial_values", []))
    values.extend([0] * max(0, 3 - len(values)))
    point_scales = {"温度": 10, "湿度": 10, "状态": 1}
    report_topic = mqtt_config["topic"]
    alarm_topic = mqtt_config["alarm_topic"]

    try:
        slave = ManagedModbusServer(
            build_context(config),
            config.get("modbus", {}).get("unit_id", 1),
            serial_config,
        )
        slave.start()
        normal_points = {
            point: (values[index], point_scales[point], 0)
            for index, point in enumerate(point_scales)
        }
        run_phase(
            probe, "正常点位", report_topic, normal_points, args.timeout
        )

        slave.set_registers(0, [850])
        probe.drain()
        run_phase(
            probe,
            "阈值告警",
            alarm_topic,
            {"温度": (850, point_scales["温度"], 1)},
            args.timeout,
        )

        slave.set_registers(0, [values[0]])
        probe.drain()
        run_phase(
            probe,
            "告警恢复",
            report_topic,
            {"温度": (values[0], point_scales["温度"], 0)},
            args.timeout,
        )
    finally:
        try:
            if slave is not None:
                slave.stop()
        finally:
            probe.close()

    print("[PASS] 全流程完成；从站、MQTT 订阅和 COM11 均已释放。", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("[STOP] 用户中断；验收程序正在清理资源。", file=sys.stderr, flush=True)
        sys.exit(130)
    except Exception as error:
        print("[FAIL] {}: {}".format(type(error).__name__, error), file=sys.stderr)
        sys.exit(1)
