#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模拟板卡数据源：无板 / 无 485 时向 MQTT 发送板卡同格式消息，供运维看板演示。

流程：boot -> 周期心跳（默认 15s）-> 每秒 3 点位（温度/湿度/状态）；
--alarm 时第 8 秒起温度拉到 850（超过阈值 800）并持续告警。

运行：先激活项目 venv（../.venv/Scripts/Activate.ps1），再 python sim_device.py [config.yaml]
      [--device 名称] [--interval 15] [--duration 0] [--alarm]
依赖：paho-mqtt>=2,<3  pyyaml
"""

import argparse
import json
import random
import time
from pathlib import Path

import yaml
import paho.mqtt.client as mqtt

CONFIG_DEFAULT = Path(__file__).resolve().parent.parent / "config.yaml"

POINTS = [
    {"name": "温度", "scale": 10, "base": 235},
    {"name": "湿度", "scale": 10, "base": 560},
    {"name": "状态", "scale": 1, "base": 1},
]
ALARM_THRESHOLD = 800
ALARM_START_TICK = 8


def main():
    """解析参数、连接 Broker，并按周期发布 boot、心跳与点位数据。"""
    parser = argparse.ArgumentParser(description="模拟板卡 MQTT 数据源")
    parser.add_argument("config", nargs="?", default=str(CONFIG_DEFAULT))
    parser.add_argument("--device", default="模拟板卡 sim01")
    parser.add_argument("--interval", type=int, default=15, help="心跳周期（秒）")
    parser.add_argument("--duration", type=int, default=0, help="运行时长（秒），0 = 一直运行")
    parser.add_argument("--alarm", action="store_true", help="第 8 秒起触发温度告警")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    mqtt_cfg = cfg["mqtt"]
    report_topic = mqtt_cfg["topic"]
    alarm_topic = mqtt_cfg["alarm_topic"]

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sim_device")
    client.connect_async(mqtt_cfg["broker"], mqtt_cfg.get("port", 1883))
    client.loop_start()

    def publish(topic, payload):
        client.publish(topic, json.dumps(payload, ensure_ascii=False))

    publish(report_topic, {"device": args.device, "ip": "192.168.43.99", "boot": 1})
    print("[sim] device={} interval={}s alarm={}".format(args.device, args.interval, args.alarm))

    start = time.time()
    tick = 0
    last_heartbeat = -1.0
    try:
        while True:
            elapsed = time.time() - start
            if args.duration and elapsed >= args.duration:
                break

            tick += 1
            for point in POINTS:
                raw = point["base"]
                if point["name"] != "状态":
                    raw += random.randint(-3, 3)
                if args.alarm and point["name"] == "温度" and tick >= ALARM_START_TICK:
                    raw = 850
                alarm = 1 if raw >= ALARM_THRESHOLD else 0
                payload = {"device": args.device, "point": point["name"],
                           "raw": raw, "scale": point["scale"], "alarm": alarm}
                publish(alarm_topic if alarm else report_topic, payload)

            if last_heartbeat < 0 or elapsed - last_heartbeat >= args.interval - 0.5:
                publish(report_topic, {"device": args.device, "ip": "192.168.43.99",
                                       "uptime": int(elapsed)})
                last_heartbeat = elapsed

            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()

    print("[sim] done")


if __name__ == "__main__":
    main()
