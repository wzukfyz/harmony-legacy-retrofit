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

static const DeviceProfile *g_dev;

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
    }

    while (1) {
        uint8_t i;

        for (i = 0; i < g_dev->point_num; i++) {
            const DevicePoint *point = &g_dev->points[i];
            uint16_t raw = 0;

            if (proto->read_regs(g_dev->slave, point->addr, &raw, 1) == 0) {
                ReportPoint(point, raw);
            }
        }
        osDelay(g_dev->poll_ms);
    }
}

static void ProjectEntry(void)
{
    printf("[project] start\r\n");

    osThreadAttr_t attr = {0};
    attr.name = "ProjectTask";
    attr.stack_size = 2048;
    attr.priority = osPriorityNormal;

    if (osThreadNew((osThreadFunc_t)ProjectTask, NULL, &attr) == NULL) {
        printf("[project] create task failed\r\n");
    }
}
SYS_RUN(ProjectEntry);
