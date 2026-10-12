#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Modbus RTU 从站模拟器（PC 侧）：模拟存量设备供 Hi3861 主机轮询。

运行：先激活项目 venv（../.venv/Scripts/Activate.ps1），再 python slave_rtu.py [config.yaml]（默认读取 ../config.yaml）
依赖：pymodbus>=3,<4  pyserial  pyyaml

注：板卡未到货前，如需 TCP 预演，可参考 pymodbus 的 StartAsyncTcpServer
    将 framer/port 改为 TCP 参数（本文件先提供 RTU 版本）。
"""

import sys
from pathlib import Path

import yaml
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)

CONFIG_DEFAULT = Path(__file__).resolve().parent.parent / "config.yaml"


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_context(cfg):
    modbus = cfg.get("modbus", {})
    registers = cfg.get("registers", {})
    base = registers.get("base_address", 0)
    values = registers.get("initial_values", [0] * 16)

    hr_block = ModbusSequentialDataBlock(base, values)
    try:
        # pymodbus 3.0 ~ 3.7：支持 zero_mode，块地址与配置的 0 基地址一致
        slave = ModbusSlaveContext(
            hr=hr_block,
            ir=hr_block,
            co=ModbusSequentialDataBlock(0, [False] * 16),
            di=ModbusSequentialDataBlock(0, [False] * 16),
            zero_mode=True,
        )
    except TypeError:
        # pymodbus >= 3.8：zero_mode 被移除，内部寻址固定 1 基（请求地址 +1），
        # 数据块地址需 +1 补偿后才能与 tools/config.yaml 的 0 基地址对齐
        hr_block = ModbusSequentialDataBlock(base + 1, values)
        slave = ModbusSlaveContext(
            hr=hr_block,
            ir=hr_block,
            co=ModbusSequentialDataBlock(1, [False] * 16),
            di=ModbusSequentialDataBlock(1, [False] * 16),
        )
    return ModbusServerContext(slaves={modbus.get("unit_id", 1): slave}, single=False)


def main():
    cfg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else CONFIG_DEFAULT
    cfg = load_config(cfg_path)
    context = build_context(cfg)
    serial_cfg = cfg["serial"]
    print("[sim] RTU serving on {} @ {} 8{}{}".format(
        serial_cfg["port"],
        serial_cfg["baudrate"],
        serial_cfg.get("parity", "N"),
        serial_cfg.get("stopbits", 1),
    ))
    print("[sim] config: {}".format(cfg_path))

    try:
        # pymodbus >= 3.6（异步 API）
        import asyncio

        from pymodbus import FramerType
        from pymodbus.server import StartAsyncSerialServer

        asyncio.run(
            StartAsyncSerialServer(
                context,
                framer=FramerType.RTU,
                port=serial_cfg["port"],
                baudrate=serial_cfg["baudrate"],
                bytesize=8,
                parity=serial_cfg.get("parity", "N"),
                stopbits=serial_cfg.get("stopbits", 1),
            )
        )
    except ImportError:
        # pymodbus 3.0 ~ 3.5（同步 API）
        from pymodbus.server import StartSerialServer
        from pymodbus.transaction import ModbusRtuFramer

        StartSerialServer(
            context,
            framer=ModbusRtuFramer,
            port=serial_cfg["port"],
            baudrate=serial_cfg["baudrate"],
            bytesize=8,
            parity=serial_cfg.get("parity", "N"),
            stopbits=serial_cfg.get("stopbits", 1),
        )


if __name__ == "__main__":
    main()
