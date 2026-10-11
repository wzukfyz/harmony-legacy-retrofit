/**
 * @file    profile_template.c
 * @brief   新设备适配模板：复制本文件 -> 填点位表 -> 新建对应头文件 ->
 *          在 device_profile.c 中按宏返回（步骤见 docs/协议适配指南.md）
 */

#include "profile_template.h"

/* TODO: 按目标设备手册填写（以下示例行仅为占位） */
static const DevicePoint g_templatePoints[] = {
    {"示例点位", 0x0000, 1, 0},
};

const DeviceProfile g_templateProfile = {
    .name = "新设备（请修改）",
    .slave = 1,
    .poll_ms = 1000,
    .point_num = sizeof(g_templatePoints) / sizeof(g_templatePoints[0]),
    .points = g_templatePoints,
};
