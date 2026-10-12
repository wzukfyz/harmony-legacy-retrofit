/**
 * @file    wifi_conn.c
 * @brief   Wi-Fi STA 连接：封装普中 BSP（bsp_wifi.c），提供带重试的连接接口
 */

#include <stdio.h>

#include "wifi_conn.h"
#include "app_config.h"
#include "bsp_wifi.h"

#define WIFI_CONNECT_RETRY      3

/* 最近一次连接成功时的 IP，供启动心跳等上报场景读取 */
static char g_wifiIp[20] = {0};

int WifiConn_Connect(void)
{
    int i;

    for (i = 1; i <= WIFI_CONNECT_RETRY; i++) {
        if (WiFi_connectHotspots(APP_WIFI_SSID, APP_WIFI_PASSWORD) == WIFI_SUCCESS) {
            (void)snprintf(g_wifiIp, sizeof(g_wifiIp), "%s", WiFi_GetLocalIP());
            printf("[project] wifi connected, ip=%s\r\n", g_wifiIp);
            return 0;
        }
        printf("[project] wifi connect failed, retry %d/%d\r\n",
               i, WIFI_CONNECT_RETRY);
    }
    return -1;
}

const char *WifiConn_GetIp(void)
{
    return g_wifiIp;
}
