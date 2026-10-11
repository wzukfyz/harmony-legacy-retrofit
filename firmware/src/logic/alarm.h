/**
 * @file    alarm.h
 * @brief   通用阈值告警判断（阈值来自各设备 profile 点位定义）
 */

#ifndef ALARM_H
#define ALARM_H

#include <stdint.h>

/**
 * @brief  判断原始值是否触发告警
 * @param  raw       原始寄存器值
 * @param  alarm_max 告警上限（0 = 该点位不告警）
 * @return 1 告警，0 正常
 */
int Alarm_Check(uint16_t raw, uint16_t alarm_max);

#endif
