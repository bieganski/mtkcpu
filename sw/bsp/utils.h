#include "periph_baseaddr.h"
#include "gpio.h"
#include "stdint.h"

void sleep(uint32_t us);

int print(const char *format, ...);

void gpio_on(uint32_t offset);

void gpio_off(uint32_t offset);

void enable_green_led();

void disable_green_led();

void enable_red_led();

void disable_red_led();