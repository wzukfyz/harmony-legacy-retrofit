/**
 * @file    device_profile.h
 * @brief   设备适配层：一个设备 = 一个 profile（点位表），业务与协议代码均不感知设备差异
 */

#ifndef DEVICE_PROFILE_H
#define DEVICE_PROFILE_H

#include <stdint.h>

/* 单个采集点位 */
typedef struct {
    const char *name;        /* 量名，如 "温度" */
    uint16_t addr;           /* 保持寄存器地址（0 基址） */
    uint16_t scale;          /* 缩放：工程量 = 原始值 / scale（scale=10 表示 0.1 单位） */
    uint16_t alarm_max;      /* 告警上限（原始值），0 = 不告警 */
} DevicePoint;

/* 一个设备 / 从站的完整适配定义 */
typedef struct {
    const char *name;        /* 设备名称，如 "普中演示从站 v1" */
    uint8_t  slave;          /* Modbus 从站地址 */
    uint16_t poll_ms;        /* 轮询周期 */
    uint8_t  point_num;
    const DevicePoint *points;
} DeviceProfile;

/* 返回当前启用的 profile（由 app_config.h 宏切换，见 device_profile.c） */
const DeviceProfile *DeviceProfile_Get(void);

#endif
