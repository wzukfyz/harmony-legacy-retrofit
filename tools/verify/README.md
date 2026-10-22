# RS485 闭环验收

从项目目录激活虚拟环境后运行：

```powershell
.\.venv\Scripts\Activate.ps1
python tools\verify\verify_rs485.py
```

脚本一次性检查正常三点位、温度告警（850）和告警恢复，并直接订阅 MQTT
结果，不依赖常驻看板或 `monitor.py`。从站与交互演示共用 `modbus_sim/managed_server.py`，
在受管线程中运行；验收结束或异常时自动关闭串口和 MQTT 订阅。默认每阶段最多等待
25 秒，可用 `--timeout 40` 调整。验收前须保证 Broker 可达、配置中的串口空闲、板卡已启动。

看板可与自动验收同时运行以观察过程；不要同时启动 `slave_rtu.py`，否则会争用 USB-RS485 串口。
验收期间不能再运行交互模式。自动验收结束后会退出并释放 COM 口。

默认从站数据来自 `tools/config.yaml`，告警阶段只在内存中临时把温度寄存器改为
850，恢复阶段改回原值，不会改写配置文件。验收通过时会打印各阶段结果和耗时。
