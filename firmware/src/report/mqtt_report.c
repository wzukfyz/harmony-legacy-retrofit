/**
 * @file    mqtt_report.c
 * @brief   MQTT 上报：封装普中 BSP MQTT 客户端（bsp_mqtt.c），发送失败时自动重连一次
 */

#include <string.h>

#include "mqtt_report.h"
#include "app_config.h"
#include "bsp_mqtt.h"

/* 建立 TCP 连接并完成 MQTT CONNECT 握手；返回 0 表示就绪 */
static int MqttReport_Connect(void)
{
    if (MQTTClient_connectServer(APP_MQTT_BROKER_IP, APP_MQTT_BROKER_PORT) != 0) {
        return -1;
    }
    return MQTTClient_init(APP_MQTT_CLIENT_ID,
                           APP_MQTT_USERNAME,
                           APP_MQTT_PASSWORD);
}

int MqttReport_Init(void)
{
    return MqttReport_Connect();
}

int MqttReport_Publish(const char *topic, const char *payload)
{
    int payload_len = (int)strlen(payload);

    if (MQTTClient_pub((char *)topic, (unsigned char *)payload, payload_len) == 0) {
        return 0;
    }

    /* 发送失败通常意味着 TCP 链路已断开：重建连接后重发一次 */
    (void)MQTTClient_unConnectServer();
    if (MqttReport_Connect() != 0) {
        return -1;
    }
    return MQTTClient_pub((char *)topic, (unsigned char *)payload, payload_len);
}
