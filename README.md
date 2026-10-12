# 存量设备低成本鸿蒙化改造模组

> 开源鸿蒙创新创业大赛 · 产品鸿蒙化方向（硬件终端）参赛项目。
> 给泵阀、电气零部件、汽摩配等存量设备加装外置采集模组，形成只读数据闭环。

**RS485/Modbus 读取 → Hi3861（OpenHarmony 轻量系统）解析 → Wi-Fi/MQTT 上报 → 本地上位机看板/告警**

- 首版只读：不写 PLC、不控制设备、不改原控制回路
- 设备端：普中-Hi3861 开发板（OpenHarmony 轻量系统 + C）
- PC 侧：Python 模拟 Modbus 从站 + 本地 MQTT Broker + 看板（Python 3.9）

## 特性

- **协议易适配**：协议层（`firmware/src/protocol/`）与设备层（`firmware/src/device/profiles/`）解耦。
  适配新设备 = 新增一个 profile 文件；接入新协议 = 新增一个 `ProtocolOps` 实现，业务代码零改动
- **全链路可离线预演**：PC 侧 pymodbus 从站 + Mosquitto + 看板脚本，板卡未到货也能先跑协议
- **中央运维终端看板**：设备在线判定（15s 周期心跳）、点位实时刷新、告警高亮；无硬件时可用模拟数据源演示
- 精简固件骨架：Modbus RTU 主站（UART1）、Wi-Fi STA、MQTT 上报、阈值告警、周期心跳

## 目录结构

```text
src/project/
├── firmware/               # 板端固件（参与 OpenHarmony 构建）
│   ├── BUILD.gn
│   ├── include/app_config.h
│   └── src/
│       ├── main.c          # 业务主流程：轮询 -> 告警 -> 上报
│       ├── protocol/       # 协议层（Modbus RTU 主站，UART1 = IO0/IO1）
│       ├── device/         # 设备适配层（profiles 点位表，“协议易适配”核心）
│       ├── report/         # Wi-Fi / MQTT 上报
│       └── logic/          # 阈值告警判断
├── tools/                  # PC 侧工具（不参与固件编译）
│   ├── config.yaml         # 串口 / Broker / 寄存器统一配置
│   ├── modbus_sim/         # pymodbus 从站模拟器
│   ├── mqtt/               # 轻量 MQTT 订阅工具
│   ├── ops/                # 中央运维系统终端看板（正式交付）
│   └── sim/                # 模拟板卡数据源（测试 / 演示资产）
├── docs/                   # 试行手册 / 协议适配指南 / 寄存器映射表
└── 补充说明.md              # 工程外改动与构建注意（必读）
```

## 快速开始

### PC 侧（项目专属 venv，Python 3.9）

```powershell
cd src\project
py -3.9 -m venv .venv                    # 首次创建（已存在可跳过）
.\.venv\Scripts\Activate.ps1             # 激活项目 venv，之后统一用 python
python -m pip install -r tools\requirements.txt

# Modbus 从站模拟器（先在 tools\config.yaml 填 USB-RS485 的 COM 口）
python tools\modbus_sim\slave_rtu.py
# MQTT 轻量订阅（快速查看原始报文）
python tools\mqtt\monitor.py
# 中央运维系统终端看板（设备在线 / 点位 / 告警实时刷新）
python tools\ops\ops_console.py
# 模拟板卡数据源（无板 / 无 485 演示；--alarm 触发告警）
python tools\sim\sim_device.py --duration 60 --alarm
```

> 激活报"禁止运行脚本"时，先执行一次：`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`（或改用 cmd 的 `.\.venv\Scripts\activate.bat`）。

### 板端（Hi3861）

在 `src\applications\sample\wifi-iot\app\BUILD.gn` 的 features 中接入本项目：

```gn
features = [
    "//project/firmware:project",
]
```

编辑 `firmware/include/app_config.h` 填 Wi-Fi / MQTT 参数后，用 DevEco 或 `hb build` 编译并烧录。

## 自主测试（无需按 RST）

设备上电后每 ~15s 自主心跳上报（`APP_HEARTBEAT_S` 可调，设 0 关闭），测试无需重放复位；
看板「设备」表出现「● 在线」且心跳秒数递增即正常，超过 60s 未收到消息判离线。

```powershell
.\.venv\Scripts\Activate.ps1

# 1) 起运维看板：实时观察在线状态 / 点位 / 告警
python tools\ops\ops_console.py
# 2) 脚本化验收：运行 N 秒后输出一帧快照并退出（适合留档 / CI）
python tools\ops\ops_console.py --snapshot 30
# 3) 无硬件演示：模拟板卡数据源（boot + 心跳 + 点位 + 告警）
python tools\sim\sim_device.py --duration 60 --alarm
```

详见 [初版试行手册 §6](docs/初版试行手册.md)。

## 硬件接线摘要（普中-Hi3861）

- TTL-RS485 模块 DI（TXD 输入）→ IO0（板子 UART1_TXD）
- TTL-RS485 模块 RO（RXD 输出）→ IO1（板子 UART1_RXD）
- VCC / GND → 3.3V / GND（必须共地）；模块带 DE/RE 时接 IO8（需启用 `app_config.h` 宏）
- 烧录与日志固定走 UART0（IO3/IO4，115200 8N1），IO0/IO1 为 RS485 专用

## 文档

- [初版试行手册](docs/初版试行手册.md)：接线表 + Day-1 步骤与验收标准
- [协议适配指南](docs/协议适配指南.md)：新增设备 / 协议三步走
- [寄存器映射表](docs/寄存器映射表.md)：点位约定（与 profile_demo.c 同步）
- [补充说明](补充说明.md)：工程外改动（hb 编码修复、编译接入）与引脚占用

## 许可与来源

- 本项目代码以 Apache License 2.0 发布（完整文本见 SDK 树根 `LICENSE`）
- 固件复用普中科技 BSP（`vendor/pzkj/pz_hi3861/common/bsp`），保留其原始版权与许可
- MQTT 协议栈使用 paho.mqtt.embedded-c（`third_party/paho.mqtt.embedded-c`，EPL/EDL 双许可）
