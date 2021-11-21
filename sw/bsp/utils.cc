#include <stdint.h>

#include "periph_baseaddr.h"
#include "gpio.h"
#include "uart.h"

#define __STRINGIFY(x) #x
#define _STRINGIFY(x) __STRINGIFY(x)
#define _FILE_LOCATION __FILE__ ":" _STRINGIFY(__LINE__)
#define ASSERT(x) _assert((x), _FILE_LOCATION " assertion failed: " #x)



#define CYC_PER_INSTR 10
constexpr uint32_t instr_per_ms = 1000 / CYC_PER_INSTR;

void sleep(uint32_t ms) {
    volatile auto num_instr = instr_per_ms * ms;
    while (num_instr) {
        num_instr--;
    }
}

// int print(const char *format, ...) {
//     // TODO 
//     return 1;
// }

void uart_putc(char c) {
    while(*((volatile uint32_t*)__tx_busy_addr));
    *((volatile uint8_t*)__tx_data_addr) = c;
}

void print(const char* msg) {
    char c;
    while(c = *(msg++)) {
        uart_putc(c);
    }
    uart_putc('\n');
}

static void _assert(int x, const char *msg) {
  if (!x) {
    print(msg);
    while(true) {}
  }
}

static inline uint32_t all_ones_but_one(uint32_t zero_offset) {
    ASSERT(zero_offset < 32);
    return 0xffffffff ^ (1 << zero_offset);
}

void gpio_set_state(uint32_t offset, bool high) {
    auto gpio_state = (volatile uint32_t*)__gpio_state_addr;
    auto old_value_masked = *gpio_state & all_ones_but_one(offset);
    *gpio_state = old_value_masked | ((high ? 1 : 0) << offset);
}

void gpio_on(uint32_t offset) {
    gpio_set_state(offset, true);
}

void gpio_off(uint32_t offset) {
    gpio_set_state(offset, false);
}

void enable_green_led() {
    gpio_on(__led_g_0__o___gpio_state_addr_offset);
}

void disable_green_led() {
    gpio_off(__led_g_0__o___gpio_state_addr_offset);
}


void enable_red_led() {
    gpio_on(__led_r_0__o___gpio_state_addr_offset);
}

void disable_red_led() {
    gpio_off(__led_r_0__o___gpio_state_addr_offset);
}