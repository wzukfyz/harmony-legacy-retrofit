/**
 * @file    modbus_rtu.c
 * @brief   Modbus RTU 主站实现（协议层）：UART1 收发 + 组帧 / CRC16 / 应答校验
 *          硬件：IO0=UART1_TXD、IO1=UART1_RXD（接线见 docs/初版试行手册.md）
 */

#include "modbus_rtu.h"
#include "app_config.h"

#include "hi_gpio.h"
#include "hi_io.h"
#include "hi_uart.h"

#define MODBUS_FC_READ_HOLDING  0x03
#define MODBUS_FC_EXCEPTION     0x80    /* 应答帧功能码最高位置 1 表示异常应答 */
#define MODBUS_REQ_LEN          8       /* 从站地址 + 功能码 + 地址 + 数量 + CRC16 */
#define MODBUS_RSP_OVERHEAD     5       /* 从站地址 + 功能码 + 字节数 + CRC16 */
#define MODBUS_RSP_MAX_LEN      256
#define MODBUS_TIMEOUT_MS       500
#define MODBUS_RETRY_COUNT      1

#define UART1_TX_PIN            HI_IO_NAME_GPIO_0
#define UART1_TX_GPIO_FUN       HI_IO_FUNC_GPIO_0_UART1_TXD
#define UART1_RX_PIN            HI_IO_NAME_GPIO_1
#define UART1_RX_GPIO_FUN       HI_IO_FUNC_GPIO_1_UART1_RXD

/* 计算 Modbus 报文 CRC16（多项式 0xA001，报文内低字节在前） */
static uint16_t Crc16_Modbus(const uint8_t *data, uint16_t len)
{
    uint16_t crc = 0xFFFF;
    uint16_t i;
    uint8_t j;

    for (i = 0; i < len; i++) {
        crc ^= data[i];
        for (j = 0; j < 8; j++) {
            if (crc & 0x0001) {
                crc = (crc >> 1) ^ 0xA001;
            } else {
                crc >>= 1;
            }
        }
    }
    return crc;
}

/* 初始化 UART1 引脚复用、RS485 方向控制（可选）与串口参数 */
static int ModbusRtu_Init(void)
{
    hi_uart_attribute attr = {0};

    hi_gpio_init();

    hi_io_set_pull(UART1_TX_PIN, HI_IO_PULL_UP);
    hi_io_set_func(UART1_TX_PIN, UART1_TX_GPIO_FUN);
    hi_gpio_set_dir(UART1_TX_PIN, HI_GPIO_DIR_OUT);

    hi_io_set_pull(UART1_RX_PIN, HI_IO_PULL_NONE);
    hi_io_set_func(UART1_RX_PIN, UART1_RX_GPIO_FUN);
    hi_gpio_set_dir(UART1_RX_PIN, HI_GPIO_DIR_IN);

#ifdef APP_RS485_DE_PIN
    hi_io_set_func(APP_RS485_DE_PIN, APP_RS485_DE_GPIO_FUN);
    hi_gpio_set_dir(APP_RS485_DE_PIN, HI_GPIO_DIR_OUT);
    hi_gpio_set_ouput_val(APP_RS485_DE_PIN, HI_GPIO_VALUE0);
#endif

    attr.baud_rate = APP_RS485_BAUDRATE;
    attr.data_bits = HI_UART_DATA_BIT_8;
    attr.stop_bits = HI_UART_STOP_BIT_1;
    attr.parity = HI_UART_PARITY_NONE;

    return (hi_uart_init(HI_UART_IDX_1, &attr, NULL) == 0) ? 0 : -1;
}

/* 发送一帧；使用带 DE/RE 的模块时，在发送前后切换收发方向 */
static void ModbusRtu_SendFrame(const uint8_t *frame, uint16_t len)
{
#ifdef APP_RS485_DE_PIN
    hi_gpio_set_ouput_val(APP_RS485_DE_PIN, HI_GPIO_VALUE1);
#endif

    (void)hi_uart_write(HI_UART_IDX_1, frame, len);

#ifdef APP_RS485_DE_PIN
    hi_gpio_set_ouput_val(APP_RS485_DE_PIN, HI_GPIO_VALUE0);
#endif
}

/* 在超时窗口内读满 expect_len 字节；不足返回 -1。
 * Modbus RTU 的 3.5 字符帧间隔在 v0.1 中由读超时兜底，不单独计时 */
static int ModbusRtu_RecvFrame(uint8_t *buf, uint16_t expect_len)
{
    uint16_t got = 0;

    while (got < expect_len) {
        hi_s32 n = hi_uart_read_timeout(HI_UART_IDX_1, buf + got,
                                        expect_len - got, MODBUS_TIMEOUT_MS);
        if (n <= 0) {
            break;
        }
        got += (uint16_t)n;
    }
    return (got == expect_len) ? 0 : -1;
}

static int ModbusRtu_ReadRegs(uint8_t slave, uint16_t addr, uint16_t *buf, uint16_t len)
{
    uint8_t req[MODBUS_REQ_LEN];
    uint8_t rsp[MODBUS_RSP_MAX_LEN];
    uint16_t expect_len;
    uint16_t crc;
    uint16_t i;
    int attempt;

    if (buf == NULL || len == 0 ||
        len > (MODBUS_RSP_MAX_LEN - MODBUS_RSP_OVERHEAD) / 2) {
        return -1;
    }
    expect_len = MODBUS_RSP_OVERHEAD + 2 * len;

    /* 组请求帧：从站地址 + 0x03 + 起始地址 + 寄存器数 + CRC16 */
    req[0] = slave;
    req[1] = MODBUS_FC_READ_HOLDING;
    req[2] = (uint8_t)(addr >> 8);
    req[3] = (uint8_t)(addr & 0xFF);
    req[4] = (uint8_t)(len >> 8);
    req[5] = (uint8_t)(len & 0xFF);
    crc = Crc16_Modbus(req, 6);
    req[6] = (uint8_t)(crc & 0xFF);
    req[7] = (uint8_t)(crc >> 8);

    for (attempt = 0; attempt <= MODBUS_RETRY_COUNT; attempt++) {
        ModbusRtu_SendFrame(req, MODBUS_REQ_LEN);

        if (ModbusRtu_RecvFrame(rsp, expect_len) != 0) {
            continue;
        }
        /* 异常应答说明从站明确拒绝本次请求，重试无意义 */
        if (rsp[1] == (MODBUS_FC_READ_HOLDING | MODBUS_FC_EXCEPTION)) {
            return -1;
        }
        if (rsp[1] != MODBUS_FC_READ_HOLDING || rsp[2] != 2 * (uint8_t)len) {
            continue;
        }
        crc = Crc16_Modbus(rsp, expect_len - 2);
        if (rsp[expect_len - 2] != (uint8_t)(crc & 0xFF) ||
            rsp[expect_len - 1] != (uint8_t)(crc >> 8)) {
            continue;
        }
        for (i = 0; i < len; i++) {
            buf[i] = (uint16_t)(((uint16_t)rsp[3 + 2 * i] << 8) | rsp[4 + 2 * i]);
        }
        return 0;
    }
    return -1;
}

const ProtocolOps g_modbusRtuOps = {
    .name = "modbus-rtu",
    .init = ModbusRtu_Init,
    .read_regs = ModbusRtu_ReadRegs,
};
