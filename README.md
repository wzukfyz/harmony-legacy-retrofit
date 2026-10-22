# 存量设备低成本鸿蒙化改造模组

> 开源鸿蒙创新创业大赛 · 产品鸿蒙化方向（硬件终端）参赛项目。
> 给泵阀、电气零部件、汽摩配等存量设备加装外置采集模组，形成只读数据闭环。

**RS485/Modbus 读取 → Hi3861（OpenHarmony 轻量系统）解析 → Wi-Fi/MQTT 上报 → 本地上位机看板/告警**

- 首版只读：不写 PLC、不控制设备、不改原控制回路
- 设备端：普中-Hi3861 开发板（OpenHarmony 轻量系统 + C）
- PC 侧：Python 模拟 Modbus 从站 + 本地 MQTT Broker + 看板（Python 3.9）

## 当前进展

- 已完成实验室完整链路：PC Modbus 从站模拟器 ⇄ USB-RS485 ⇄ MAX3485 ⇄ Hi3861/OpenHarmony ⇄ 2.4GHz Wi-Fi/MQTT ⇄ PC 看板。
- 已实测温度、湿度、状态三个点位，以及温度超限告警（raw=850）和恢复；真实工业设备接入与长时可靠性测试仍待开展。
- 固件轮询配置为 `poll_ms=1000`；Hi3861 LiteOS-M tick 为 100Hz，板端实际约每 10 秒完成一轮点位轮询，非每秒刷新。

## 特性

- **协议易适配**：协议层（`firmware/src/protocol/`）与设备层（`firmware/src/device/profiles/`）解耦。
  适配新设备 = 新增一个 profile 文件；接入新协议 = 新增一个 `ProtocolOps` 实现，业务代码零改动
- **完整硬件闭环**：PC 侧 pymodbus 从站经 USB-RS485 与板端 MAX3485 通信，板端再经 Wi-Fi/MQTT 上报
- **中央运维终端看板**：设备在线判定（约 15s 心跳）、点位轮询更新、告警高亮
- **人工调值演示**：交互式从站支持运行中修改温度、湿度、状态及原始寄存器
- **限时自动验收**：一条命令验证正常点位、告警与恢复，退出时释放串口
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
│   ├── sim/                # 无板/无485时的 MQTT 模拟板卡（备用）
│   └── verify/             # 限时 RS485/MQTT 闭环验收
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

# 常驻人工演示：终端 1，支持 help / show / temp / humidity / status / alarm / normal / quit
python tools\modbus_sim\slave_rtu.py --interactive
# 常驻运维看板：终端 2
python tools\ops\ops_console.py
# 独立自动验收（与交互式从站互斥，二者不能同时占用 USB-RS485 COM 口）
python tools\verify\verify_rs485.py
```

交互式演示中输入 `temp 35.6`、`humidity 65` 可实时改寄存器，输入 `alarm` 触发温度告警，输入 `normal` 恢复启动时数据。板端下一轮轮询后看板更新（实测约 10 秒一轮）。

> 激活报"禁止运行脚本"时，先执行一次：`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`（或改用 cmd 的 `.\.venv\Scripts\activate.bat`）。

### 板端（Hi3861）

在 `src\applications\sample\wifi-iot\app\BUILD.gn` 的 features 中接入本项目：

```gn
features = [
    "//project/firmware:project",
]
```

编辑 `firmware/include/app_config.h` 填 Wi-Fi / MQTT 参数后，用 DevEco 或 `hb build` 编译并烧录。

## 自动验收与备用模拟（无需按 RST）

设备上电后每 ~15s 自主心跳上报（`APP_HEARTBEAT_S` 可调，设 0 关闭），测试无需重放复位；
看板「设备」表出现「● 在线」且心跳秒数递增即正常，超过 60s 未收到消息判离线。

```powershell
.\.venv\Scripts\Activate.ps1

# 需要终端留档时可输出看板快照
python tools\ops\ops_console.py --snapshot 15
# 无板或无485时的备用纯 MQTT 演示，不代表实体 RS485 采集
python tools\sim\sim_device.py --duration 60 --alarm
```

完整硬件演示与自动验收详见 [初版试行手册](docs/初版试行手册.md) 和 [验收说明](tools/verify/README.md)。

## 硬件接线摘要（普中-Hi3861）

- 模块丝印 TXD（发送输出）→ IO1（板子 UART1_RXD，P1 第 28 脚）
- 模块丝印 RXD（接收输入）→ IO0（板子 UART1_TXD，P1 第 30 脚）
- EN → IO8（P1 第 29 脚，实测高电平发送；固件已启用方向控制）
- 模块左侧 3V3/GND → P1 3.3V/GND；模块 A/B/右侧 GND → PC USB-RS485 A/B/GND
- P1 3.3V：10/12/14/16；GND：13/15/17（16 脚按实物核对为 3.3V）
- 烧录与日志固定走 UART0（IO3/IO4，115200 8N1），IO0/IO1 为 RS485 专用

## 文档

- [初版试行手册](docs/初版试行手册.md)：接线表 + Day-1 步骤与验收标准
- [Modbus 从站交互演示](tools/modbus_sim/README.md)：常驻在线人工调值、告警和恢复
- [RS485 闭环验收](tools/verify/README.md)：限时自动验收与清理说明
- [协议适配指南](docs/协议适配指南.md)：新增设备 / 协议三步走
- [寄存器映射表](docs/寄存器映射表.md)：点位约定（与 profile_demo.c 同步）
- [补充说明](补充说明.md)：工程外改动（hb 编码修复、编译接入）与引脚占用

## 许可与来源

- 本项目代码以 Apache License 2.0 发布（完整文本见 SDK 树根 `LICENSE`）
- 固件复用普中科技 BSP（`vendor/pzkj/pz_hi3861/common/bsp`），保留其原始版权与许可
- MQTT 协议栈使用 paho.mqtt.embedded-c（`third_party/paho.mqtt.embedded-c`，EPL/EDL 双许可）
