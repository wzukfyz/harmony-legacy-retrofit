/**
 * @file    mqtt_report.h
 * @brief   MQTT 上报接口（骨架）
 */

#ifndef MQTT_REPORT_H
#define MQTT_REPORT_H

/**
 * @brief  初始化并连接 app_config.h 中配置的 Broker
 * @return 0 成功，非 0 失败
 */
int MqttReport_Init(void);

/**
 * @brief  发布一条消息
 * @param  topic   主题
 * @param  payload 负载（一般为 JSON 字符串）
 * @return 0 成功，非 0 失败
 */
int MqttReport_Publish(const char *topic, const char *payload);

#endif
