#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Modbus RTU slave simulator for the Hi3861 gateway and demo workflow.

Run with the project virtual environment. Add ``--interactive`` to change
register values while the serial server stays online.
"""

import argparse
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import shlex
import time
from pathlib import Path

import yaml
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)

from managed_server import ManagedModbusServer

CONFIG_DEFAULT = Path(__file__).resolve().parent.parent / "config.yaml"
POINTS = {
    "温度": (0, 10, "℃"),
    "湿度": (1, 10, "%RH"),
    "状态": (2, 1, ""),
}


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


def show_registers(server, base_address, register_count, alarm_threshold):
    """Prints current demo point values and the temperature threshold state."""
    values = server.get_registers(base_address, register_count)
    for name, (offset, scale, unit) in POINTS.items():
        if offset >= len(values):
            continue
        raw = values[offset]
        value = "{:.1f}".format(raw / scale) if scale > 1 else str(raw)
        state = "（告警阈值已达到）" if name == "温度" and raw >= alarm_threshold else ""
        print("{}：{}{}（raw={}）{}".format(name, value, unit, raw, state))


def parse_raw_value(value):
    """Parses an unsigned 16-bit decimal register value."""
    raw = int(value, 0)
    if raw < 0 or raw > 65535:
        raise ValueError("寄存器值必须在 0..65535 范围内")
    return raw


def scaled_raw_value(value, scale, maximum=None):
    """Converts an engineering value to a scaled unsigned register value."""
    try:
        engineering_value = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("请输入有效数字") from error
    if not engineering_value.is_finite() or engineering_value < 0:
        raise ValueError("数值必须是有限的非负数")
    if maximum is not None and engineering_value > maximum:
        raise ValueError("数值不能超过 {}".format(maximum))
    raw = int((engineering_value * scale).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return parse_raw_value(str(raw))


def print_help():
    """Prints commands supported by the interactive demo prompt."""
    print("命令：")
    print("  show                  查看当前点位")
    print("  temp <℃>              设置温度，如 temp 35.6")
    print("  humidity <%RH>        设置湿度，如 humidity 65.0")
    print("  status <原始值>        设置状态寄存器，如 status 0")
    print("  set <地址> <原始值>   按寄存器地址设置，如 set 0x0000 850")
    print("  alarm                 设置温度越限，触发板端告警")
    print("  normal                恢复启动时的寄存器值")
    print("  help                  显示帮助")
    print("  quit                  停止从站并退出")


def run_interactive(server, cfg):
    """Handles operator commands while the background RTU server stays active."""
    registers = cfg.get("registers", {})
    base_address = registers.get("base_address", 0)
    initial_values = list(registers.get("initial_values", [0] * 8))
    register_count = len(initial_values)
    alarm_threshold = cfg.get("alarm", {}).get("value_max", 800)
    alarm_raw = max(850, alarm_threshold + 1)

    print("[demo] 交互式从站已就绪。输入 help 查看命令，Ctrl+C 或 quit 退出。")
    show_registers(server, base_address, register_count, alarm_threshold)
    while True:
        try:
            parts = shlex.split(input("modbus> ").strip())
        except EOFError:
            print("\n[demo] 收到输入结束，正在关闭从站。")
            return
        if not parts:
            continue

        command = parts[0].lower()
        try:
            if command in ("quit", "exit"):
                return
            if command == "help":
                print_help()
                continue
            if command == "show":
                show_registers(server, base_address, register_count, alarm_threshold)
                continue
            if command == "normal":
                server.set_registers(base_address, initial_values)
                print("[demo] 已恢复启动时的寄存器值。")
                show_registers(server, base_address, register_count, alarm_threshold)
                continue
            if command == "alarm":
                server.set_registers(base_address, [alarm_raw])
                print("[demo] 温度寄存器已设为 {}（{}℃），等待板端轮询上报。".format(
                    alarm_raw, alarm_raw / POINTS["温度"][1]
                ))
                continue
            if command in ("temp", "humidity", "status") and len(parts) == 2:
                point_name = {"temp": "温度", "humidity": "湿度", "status": "状态"}[command]
                offset, scale, _ = POINTS[point_name]
                if command == "humidity":
                    raw = scaled_raw_value(parts[1], scale, maximum=100)
                elif command == "temp":
                    raw = scaled_raw_value(parts[1], scale)
                else:
                    raw = parse_raw_value(parts[1])
                server.set_registers(base_address + offset, [raw])
                print("[demo] {}寄存器已更新为 raw={}，等待板端轮询上报。".format(
                    point_name, raw
                ))
                continue
            if command == "set" and len(parts) == 3:
                address = int(parts[1], 0)
                raw = parse_raw_value(parts[2])
                if not base_address <= address < base_address + register_count:
                    raise ValueError("地址应在 0x{:04X}..0x{:04X} 范围内".format(
                        base_address, base_address + register_count - 1
                    ))
                server.set_registers(address, [raw])
                print("[demo] 地址 0x{:04X} 已更新为 raw={}，等待板端轮询上报。".format(
                    address, raw
                ))
                continue
            raise ValueError("命令格式不正确；输入 help 查看用法")
        except (ValueError, IndexError) as error:
            print("[demo] {}".format(error))


def main():
    parser = argparse.ArgumentParser(description="Hi3861 Modbus RTU 从站模拟器")
    parser.add_argument("config", nargs="?", default=str(CONFIG_DEFAULT))
    parser.add_argument(
        "--interactive", action="store_true", help="启用实时寄存器调值命令"
    )
    args = parser.parse_args()
    cfg_path = Path(args.config)
    cfg = load_config(cfg_path)
    context = build_context(cfg)
    serial_cfg = cfg["serial"]
    server = ManagedModbusServer(context, cfg.get("modbus", {}).get("unit_id", 1), serial_cfg)
    try:
        server.start()
        print("[sim] RTU serving on {} @ {} 8{}{}".format(
            serial_cfg["port"],
            serial_cfg["baudrate"],
            serial_cfg.get("parity", "N"),
            serial_cfg.get("stopbits", 1),
        ), flush=True)
        print("[sim] config: {}".format(cfg_path), flush=True)
        if args.interactive:
            run_interactive(server, cfg)
        else:
            print("按 Ctrl+C 停止从站。", flush=True)
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n[sim] 收到停止信号，正在释放串口。", flush=True)
    finally:
        server.stop()


if __name__ == "__main__":
    main()
