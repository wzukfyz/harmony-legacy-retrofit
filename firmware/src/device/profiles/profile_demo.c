/**
 * @file    profile_demo.c
 * @brief   演示设备适配（点位表与 docs/寄存器映射表.md 保持一致）
 */

#include "profile_demo.h"

static const DevicePoint g_demoPoints[] = {
    {"温度", 0x0000, 10, 800},
    {"湿度", 0x0001, 10,   0},
    {"状态", 0x0002,  1,   0},
};

const DeviceProfile g_demoProfile = {
    .name = "普中演示从站 v1",
    .slave = 1,
    .poll_ms = 1000,
    .point_num = sizeof(g_demoPoints) / sizeof(g_demoPoints[0]),
    .points = g_demoPoints,
};
