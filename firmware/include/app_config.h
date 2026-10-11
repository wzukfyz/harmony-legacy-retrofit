/**
 * @file    app_config.h
 * @brief   系统参数（Wi-Fi / MQTT / RS485 传输），设备点位定义见 device/profiles/
 */

#ifndef APP_CONFIG_H
#define APP_CONFIG_H

/* 设备适配选择：启用其一（新增设备：复制 profiles/profile_template.c 并在此添加宏） */
#define APP_PROFILE_DEMO        1
/* #define APP_PROFILE_TEMPLATE 1 */

/* RS485 传输：UART1 固定占用 IO0(TXD) / IO1(RXD)，接线见 docs/初版试行手册.md
 * TODO(board-arrival): 到货后按从设备手册核对波特率与校验位 */
#define APP_RS485_BAUDRATE      9600

/* RS485 收发方向控制：仅当转换模块带 DE/RE 引脚时启用（自动收发模块保持注释） */
/* #define APP_RS485_DE_PIN      HI_IO_NAME_GPIO_8 */
/* #define APP_RS485_DE_GPIO_FUN HI_IO_FUNC_GPIO_8_GPIO */

/* Wi-Fi（TODO(board-arrival): 到货联调前填写路由器 SSID / 密码） */
#define APP_WIFI_SSID           "TODO_SSID"
#define APP_WIFI_PASSWORD       "TODO_PASSWORD"

/* MQTT（TODO(board-arrival): broker 地址填 PC 在路由器下的局域网 IP） */
#define APP_MQTT_BROKER_IP      "192.168.1.100"
#define APP_MQTT_BROKER_PORT    1883
#define APP_MQTT_CLIENT_ID      "hi3861_gw_01"
#define APP_MQTT_USERNAME       "hi3861"
#define APP_MQTT_PASSWORD       "hi3861"
#define APP_MQTT_TOPIC_REPORT   "iot/dev01/report"
#define APP_MQTT_TOPIC_ALARM    "iot/dev01/alarm"

#endif
