/**
 * @file    protocol_if.h
 * @brief   协议层统一接口：业务层只依赖本接口，新增协议 = 新增一个实现文件
 */

#ifndef PROTOCOL_IF_H
#define PROTOCOL_IF_H

#include <stdint.h>

typedef struct {
    const char *name;
    int (*init)(void);
    int (*read_regs)(uint8_t slave, uint16_t addr, uint16_t *buf, uint16_t len);
} ProtocolOps;

#endif
