/**
 * @file    device_profile.c
 * @brief   设备切换入口：修改 app_config.h 的 APP_PROFILE_xxx 宏即可切换设备适配
 */

#include "app_config.h"
#include "device_profile.h"
#include "profiles/profile_demo.h"
#include "profiles/profile_template.h"

const DeviceProfile *DeviceProfile_Get(void)
{
#if defined(APP_PROFILE_TEMPLATE)
    return &g_templateProfile;
#else
    return &g_demoProfile;
#endif
}
