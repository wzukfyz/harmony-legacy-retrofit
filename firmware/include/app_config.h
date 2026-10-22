/**
 * @file    app_config.h
 * @brief   系统参数（Wi-Fi / MQTT / RS485 传输），设备点位定义见 device/profiles/
 */

#ifndef APP_CONFIG_H
#define APP_CONFIG_H

/* 设备适配选择：启用其一（新增设备：复制 profiles/profile_template.c 并在此添加宏） */
#define APP_PROFILE_DEMO        1
/* #define APP_PROFILE_TEMPLATE 1 */

/* RS485 传输：UART1 固定使用 IO0(TXD) / IO1(RXD)，9600 8N1 已完成 MAX3485 联调。 */
#define APP_RS485_BAUDRATE      9600

/* RS485 收发方向控制：EN 高电平=发送（MAX3485 手动方向模块，EN 接 IO8） */
#define APP_RS485_DE_PIN         HI_IO_NAME_GPIO_8
#define APP_RS485_DE_GPIO_FUN    HI_IO_FUNC_GPIO_8_GPIO

/* Wi-Fi（当前联调热点：iroha；换网络时同步修改） */
#define APP_WIFI_SSID           "iroha"
#define APP_WIFI_PASSWORD       "0d000721"

/* MQTT（broker = PC 在当前热点下的局域网 IP，换网后复核） */
#define APP_MQTT_BROKER_IP      "192.168.43.184"
#define APP_MQTT_BROKER_PORT    1883
#define APP_MQTT_CLIENT_ID      "hi3861_gw_01"
#define APP_MQTT_USERNAME       "hi3861"
#define APP_MQTT_PASSWORD       "hi3861"
#define APP_MQTT_TOPIC_REPORT   "iot/dev01/report"
#define APP_MQTT_TOPIC_ALARM    "iot/dev01/alarm"

/* 周期心跳（秒）：供运维系统判定在线 + MQTT 保活；设为 0 关闭周期心跳（boot 消息不受影响） */
#define APP_HEARTBEAT_S         15

#endif
