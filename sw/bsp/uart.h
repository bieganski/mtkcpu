// Code automatically generated, do not modify!

#include "periph_baseaddr.h"
/* Read only - non-zero value means UART is busy and write to tx_data will have no effect. Otherwise write to tx_data will trigger byte send. */
#define __tx_busy_addr (uart_base + 0x0)

/* Data byte to be sent. Width of this register is 8 bits. */
#define __tx_data_addr (uart_base + 0x8)

