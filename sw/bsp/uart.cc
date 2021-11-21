// Code automatically generated, do not modify!

#include "uart.h"
/* Read only - non-zero value means UART is busy and write to tx_data will have no effect. Otherwise write to tx_data will trigger byte send. */
const void* tx_busy_addr = (void*) __tx_busy_addr;

/* Data byte to be sent. Width of this register is 8 bits. */
const void* tx_data_addr = (void*) __tx_data_addr;

