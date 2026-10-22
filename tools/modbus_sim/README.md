# Modbus RTU 从站演示

先在项目目录激活 venv，并确保 `tools/config.yaml` 中的 `serial.port` 指向 USB-RS485 转换器。
交互演示需要 Hi3861 和运维看板在线；从站模拟器与自动验收互斥，任一时刻只能有一个程序占用 COM 口。

```powershell
.\.venv\Scripts\Activate.ps1
python tools\modbus_sim\slave_rtu.py --interactive
```

同时在另一个终端运行看板：

```powershell
python tools\ops\ops_console.py
```

交互终端命令：

| 命令 | 用途 | 示例 |
| --- | --- | --- |
| `show` | 查看温度、湿度、状态原始值和工程量 | `show` |
| `temp <℃>` | 设置温度，按 0.1℃ 换算寄存器 | `temp 35.6` |
| `humidity <%RH>` | 设置湿度，范围 0–100%RH | `humidity 65.0` |
| `status <值>` | 设置状态寄存器原始值 | `status 0` |
| `set <地址> <raw>` | 按寄存器地址设置原始值，可用十进制或十六进制 | `set 0x0000 356` |
| `alarm` | 将温度设置为越限值（默认 raw=850，即 85.0℃） | `alarm` |
| `normal` | 恢复启动时 `config.yaml` 的寄存器初值 | `normal` |
| `help` | 显示帮助 | `help` |
| `quit` | 关闭从站并释放 COM 口 | `quit` |

寄存器修改在运行内存中立即生效，不会改写配置文件；板端在下一轮轮询后读取并上报，当前实测轮询约 10 秒一轮。输入提示只表示模拟寄存器已更新；以看板收到的新值或告警为闭环完成依据。告警由板端固件阈值判断后发布，不是模拟器直接伪造 MQTT 告警。

也可不加 `--interactive` 启动仅响应轮询的常驻从站：

```powershell
python tools\modbus_sim\slave_rtu.py
```

退出常驻模式按 `Ctrl+C`。完整自动检查使用 `python tools\verify\verify_rs485.py`，运行时不要另开从站实例。
