#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MQTT 看板/告警订阅端（PC 侧）：订阅板上报并打印，后续可扩展 Web 看板。

运行：..\.venv\Scripts\python.exe monitor.py [config.yaml]     # 默认读取 ../config.yaml
依赖：paho-mqtt>=2,<3  pyyaml
"""

import json
import sys
from pathlib import Path

import yaml
import paho.mqtt.client as mqtt

CONFIG_DEFAULT = Path(__file__).resolve().parent.parent / "config.yaml"


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code.is_failure:
        print("[monitor] connect failed: {}".format(reason_code))
        return
    for topic in userdata["topics"]:
        client.subscribe(topic)
        print("[monitor] subscribed: {}".format(topic))


def on_message(client, userdata, msg):
    text = msg.payload.decode("utf-8", errors="replace")
    try:
        data = json.loads(text)
        print("[monitor] {}: {}".format(msg.topic, data))
    except ValueError:
        print("[monitor] {}: {}".format(msg.topic, text))
    if msg.topic == userdata["alarm_topic"]:
        print("[ALARM] {}".format(text))


def main():
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else CONFIG_DEFAULT
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    mqtt_cfg = cfg["mqtt"]
    userdata = {
        "topics": [mqtt_cfg["topic"], mqtt_cfg["alarm_topic"]],
        "alarm_topic": mqtt_cfg["alarm_topic"],
    }

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.user_data_set(userdata)
    client.on_connect = on_connect
    client.on_message = on_message

    broker = mqtt_cfg["broker"]
    port = mqtt_cfg.get("port", 1883)
    print("[monitor] connecting {}:{}".format(broker, port))
    client.connect(broker, port)
    client.loop_forever()


if __name__ == "__main__":
    main()
