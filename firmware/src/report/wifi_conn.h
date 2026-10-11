/**
 * @file    wifi_conn.h
 * @brief   Wi-Fi STA 连接接口（骨架）
 */

#ifndef WIFI_CONN_H
#define WIFI_CONN_H

/**
 * @brief  连接 app_config.h 中配置的 AP
 * @return 0 成功，非 0 失败
 */
int WifiConn_Connect(void);

#endif
