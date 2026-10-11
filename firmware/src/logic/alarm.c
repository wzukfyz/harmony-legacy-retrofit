/**
 * @file    alarm.c
 * @brief   通用阈值告警判断
 */

#include "alarm.h"

int Alarm_Check(uint16_t raw, uint16_t alarm_max)
{
    if (alarm_max == 0) {
        return 0;
    }
    return (raw >= alarm_max) ? 1 : 0;
}
