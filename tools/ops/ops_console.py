#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""中央运维系统 - 终端实时看板。

订阅 MQTT 设备消息并实时展示：设备在线状态、点位数据、告警与最近消息流。
消息类型（JSON）：
  boot      {"device", "ip", "boot": 1}
  heartbeat {"device", "ip", "uptime"}
  point     {"device", "point", "raw", "scale", "alarm"}

运行：先激活项目 venv（../.venv/Scripts/Activate.ps1），再 python ops_console.py [config.yaml] [--snapshot N]
依赖：paho-mqtt>=2,<3  rich>=13  pyyaml
"""

import argparse
import json
import threading
import time
from pathlib import Path

import yaml
import paho.mqtt.client as mqtt
from rich.console import Console
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

CONFIG_DEFAULT = Path(__file__).resolve().parent.parent / "config.yaml"

# 离线判定：超过该秒数未收到设备消息视为离线（实测心跳 15~25s，留足余量）
OFFLINE_TIMEOUT_S = 60
MAX_LOG_LINES = 8


def load_config(path):
    """读取并解析 YAML 配置。"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class OpsData:
    """看板数据模型：MQTT 线程写入，渲染线程读取（用锁保护）。

    Attributes:
        devices: 设备名 -> {ip, uptime, last_seen}。
        points: (设备名, 点位名) -> {raw, scale, alarm, ts}。
        logs: 最近 MAX_LOG_LINES 条消息 (时间, 主题, 内容)。
        msg_count: 收到的消息总数。
        last_msg_ts: 最近一条消息的时间戳。
        connected: MQTT 连接状态。
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.devices = {}
        self.points = {}
        self.logs = []
        self.msg_count = 0
        self.last_msg_ts = 0.0
        self.connected = False

    def on_message(self, topic, payload):
        """解析并入库一条 MQTT 消息；未知格式仅记入消息流。"""
        now = time.time()
        text = payload.decode("utf-8", "replace")
        with self.lock:
            self.msg_count += 1
            self.last_msg_ts = now
            self.logs.append((time.strftime("%H:%M:%S"), topic, text[:72]))
            if len(self.logs) > MAX_LOG_LINES:
                self.logs.pop(0)
        try:
            data = json.loads(text)
        except ValueError:
            return
        if not isinstance(data, dict) or "device" not in data:
            return
        with self.lock:
            dev = self.devices.setdefault(data["device"], {})
            dev["last_seen"] = now
            dev["ip"] = data.get("ip", dev.get("ip", "-"))
            if "uptime" in data:
                dev["uptime"] = data["uptime"]
            if "point" in data:
                self.points[(data["device"], data["point"])] = {
                    "raw": data.get("raw", 0),
                    "scale": data.get("scale", 1),
                    "alarm": data.get("alarm", 0),
                    "ts": now,
                }

    def snapshot_data(self):
        """加锁返回当前数据的快照元组。"""
        with self.lock:
            return (dict(self.devices), dict(self.points), list(self.logs),
                    self.msg_count, self.last_msg_ts, self.connected)


def build_devices_table(devices, now):
    """构建设备表：IP、心跳、在线状态与最近消息时间。"""
    table = Table(title="设备", expand=True)
    table.add_column("设备")
    table.add_column("IP")
    table.add_column("心跳(秒)", justify="right")
    table.add_column("状态")
    table.add_column("最近消息", justify="right")

    for name, dev in sorted(devices.items()):
        last = dev.get("last_seen", 0)
        online = last > 0 and (now - last) <= OFFLINE_TIMEOUT_S
        state = "[green]● 在线[/green]" if online else "[red]○ 离线[/red]"
        table.add_row(name, dev.get("ip", "-"), str(dev.get("uptime", "-")), state,
                      time.strftime("%H:%M:%S", time.localtime(last)) if last else "-")

    if not devices:
        table.add_row("[dim]等待设备上报...[/dim]", "", "", "", "")
    return table


def build_points_table(points, now):
    """构建点位表：原始值、工程量、告警状态与更新时间。"""
    table = Table(title="点位实时数据", expand=True)
    table.add_column("设备")
    table.add_column("点位")
    table.add_column("原始值", justify="right")
    table.add_column("工程量", justify="right")
    table.add_column("状态")
    table.add_column("更新时间", justify="right")

    for (device, point), item in sorted(points.items()):
        scale = item["scale"] or 1
        value = item["raw"] / scale
        value_text = "{:.1f}".format(value) if scale > 1 else str(item["raw"])
        alarm = item.get("alarm", 0)
        table.add_row(device, point, str(item["raw"]), value_text,
                      "[red]告警[/red]" if alarm else "[green]正常[/green]",
                      time.strftime("%H:%M:%S", time.localtime(item["ts"])),
                      style="bold red" if alarm else "")

    if not points:
        table.add_row("[dim]等待点位数据（485 联调后自动出现）[/dim]", "", "", "", "", "")
    return table


def build_logs_panel(logs):
    """构建最近消息面板（最多 MAX_LOG_LINES 条）。"""
    lines = ["[dim]{}[/dim] [cyan]{}[/cyan] {}".format(ts, topic, text)
             for ts, topic, text in logs]
    return Panel("\n".join(lines) if lines else "[dim]暂无消息[/dim]",
                 title="最近消息", expand=True)


def render(data, broker):
    """渲染一帧看板：状态栏 + 设备表 + 点位表 + 消息流。"""
    devices, points, logs, count, last_ts, connected = data.snapshot_data()
    now = time.time()
    state = "[green]● 已连接[/green]" if connected else "[red]○ 未连接[/red]"
    last_text = time.strftime("%H:%M:%S", time.localtime(last_ts)) if last_ts else "-"
    head = Panel(
        "[bold]中央运维系统[/bold]  |  Broker: {}  |  {}  |  消息: {}  |  最后: {}".format(
            broker, state, count, last_text),
        title="状态")
    return Group(head, build_devices_table(devices, now),
                 build_points_table(points, now), build_logs_panel(logs))


def main():
    """解析参数、连接 Broker，并按模式渲染看板或输出快照。"""
    parser = argparse.ArgumentParser(description="中央运维系统终端看板")
    parser.add_argument("config", nargs="?", default=str(CONFIG_DEFAULT))
    parser.add_argument("--snapshot", type=int, default=0,
                        help="运行 N 秒后打印一帧快照并退出（便于脚本化验收）")
    args = parser.parse_args()

    cfg = load_config(args.config)
    mqtt_cfg = cfg["mqtt"]
    broker = "{}:{}".format(mqtt_cfg["broker"], mqtt_cfg.get("port", 1883))
    topic_prefix = mqtt_cfg["topic"].split("/")[0] + "/#"

    console = Console()
    data = OpsData()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ops_console")

    def on_connect(client_, userdata, flags, reason_code, properties=None):
        if not reason_code.is_failure:
            client_.subscribe(topic_prefix)
            data.connected = True

    def on_disconnect(client_, userdata, flags, reason_code, properties=None):
        data.connected = False

    def on_message(client_, userdata, msg):
        data.on_message(msg.topic, msg.payload)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    client.connect_async(mqtt_cfg["broker"], mqtt_cfg.get("port", 1883))
    client.loop_start()

    try:
        if args.snapshot > 0:
            time.sleep(args.snapshot)
            Console(width=120).print(render(data, broker))
        else:
            with Live(render(data, broker), console=console,
                      refresh_per_second=4, screen=False) as live:
                while True:
                    live.update(render(data, broker))
                    time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
