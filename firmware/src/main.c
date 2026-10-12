/**
 * @file    main.c
 * @brief   业务主流程：按设备 profile 轮询点位 -> 阈值判断 -> MQTT 上报
 *          本文件不含协议帧细节与设备寄存器细节（见 protocol/ 与 device/）
 */

#include <stdio.h>
#include <unistd.h>

#include "ohos_init.h"
#include "cmsis_os2.h"

#include "app_config.h"
#include "alarm.h"
#include "device_profile.h"
#include "modbus_rtu.h"
#include "mqtt_report.h"
#include "wifi_conn.h"

/* 当前设备 profile（device 层选择，运行期只读） */
static const DeviceProfile *g_dev;

/* 按点位告警阈值组装 JSON，并发布到告警或常规上报主题 */
static void ReportPoint(const DevicePoint *point, uint16_t raw)
{
    int alarm = Alarm_Check(raw, point->alarm_max);
    char payload[96] = {0};

    (void)snprintf(payload, sizeof(payload),
                   "{\"device\":\"%s\",\"point\":\"%s\",\"raw\":%d,"
                   "\"scale\":%d,\"alarm\":%d}",
                   g_dev->name, point->name, (int)raw,
                   (int)point->scale, alarm);

    if (alarm != 0) {
        printf("[project] alarm: %s=%d\r\n", point->name, (int)raw);
        MqttReport_Publish(APP_MQTT_TOPIC_ALARM, payload);
    } else {
        MqttReport_Publish(APP_MQTT_TOPIC_REPORT, payload);
    }
}

/* 上报启动心跳：便于 485 模块到货前先验证 板卡 -> MQTT -> 看板 链路 */
static void ReportBoot(void)
{
    char payload[96] = {0};

    (void)snprintf(payload, sizeof(payload),
                   "{\"device\":\"%s\",\"ip\":\"%s\",\"boot\":1}",
                   g_dev->name, WifiConn_GetIp());
    if (MqttReport_Publish(APP_MQTT_TOPIC_REPORT, payload) == 0) {
        printf("[project] boot report sent: %s\r\n", payload);
    } else {
        printf("[project] boot report failed\r\n");
    }
}

#if (APP_HEARTBEAT_S > 0)
/* 心跳计时状态：按墙钟检查，且在每个点位读取后调用，避免受单轮循环耗时影响。
 * g_tickFreq：每秒 tick 数；g_heartbeatTicks：心跳周期（单位 tick）；g_lastHeartbeatTick：上次发送时刻 */
static uint32_t g_tickFreq;
static uint32_t g_heartbeatTicks;
static uint32_t g_lastHeartbeatTick;

/* 周期心跳：供运维系统判定设备在线，兼作 MQTT 链路保活（APP_HEARTBEAT_S = 0 时关闭） */
static void ReportHeartbeat(uint32_t uptime_s)
{
    char payload[96] = {0};

    (void)snprintf(payload, sizeof(payload),
                   "{\"device\":\"%s\",\"ip\":\"%s\",\"uptime\":%u}",
                   g_dev->name, WifiConn_GetIp(), (unsigned int)uptime_s);
    if (MqttReport_Publish(APP_MQTT_TOPIC_REPORT, payload) == 0) {
        printf("[project] heartbeat sent: uptime=%us\r\n", (unsigned int)uptime_s);
    }
}

/* 到达心跳周期时发送一次心跳；在每个点位读取后调用，降低发送抖动 */
static void HeartbeatCheck(void)
{
    uint32_t now = osKernelGetTickCount();

    if (now - g_lastHeartbeatTick >= g_heartbeatTicks) {
        g_lastHeartbeatTick = now;
        ReportHeartbeat(now / g_tickFreq);
    }
}
#endif

static void ProjectTask(void)
{
    /* 协议切换点：更换协议时替换为对应 ProtocolOps 实现 */
    const ProtocolOps *proto = &g_modbusRtuOps;

    g_dev = DeviceProfile_Get();
    printf("[project] device=%s protocol=%s points=%d\r\n",
           g_dev->name, proto->name, (int)g_dev->point_num);

    (void)proto->init();
    if (WifiConn_Connect() != 0) {
        printf("[project] wifi connect failed\r\n");
    }
    if (MqttReport_Init() != 0) {
        printf("[project] mqtt init failed\r\n");
    } else {
        ReportBoot();
    }

#if (APP_HEARTBEAT_S > 0)
    g_tickFreq = osKernelGetTickFreq();
    g_heartbeatTicks = (uint32_t)APP_HEARTBEAT_S * g_tickFreq;
    g_lastHeartbeatTick = osKernelGetTickCount();
#endif

    while (1) {
        uint8_t i;

        for (i = 0; i < g_dev->point_num; i++) {
            const DevicePoint *point = &g_dev->points[i];
            uint16_t raw = 0;

            if (proto->read_regs(g_dev->slave, point->addr, &raw, 1) == 0) {
                ReportPoint(point, raw);
            }
#if (APP_HEARTBEAT_S > 0)
            HeartbeatCheck();
#endif
        }
        osDelay(g_dev->poll_ms);
    }
}

static void ProjectEntry(void)
{
    printf("[project] start\r\n");

    osThreadAttr_t attr = {0};
    attr.name = "ProjectTask";
    /* Wi-Fi/MQTT 调用链较深（参考普中 wifi/mqtt demo 的 10KB 栈配置） */
    attr.stack_size = 1024 * 10;
    attr.priority = osPriorityNormal;

    if (osThreadNew((osThreadFunc_t)ProjectTask, NULL, &attr) == NULL) {
        printf("[project] create task failed\r\n");
    }
}
SYS_RUN(ProjectEntry);
