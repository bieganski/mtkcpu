#include "utils.h"
#include "uart.h"

int main() {
	auto sleep_time_ms = 1000;
	while(true) {
		print("Hello from mtkCPU!");
		sleep(sleep_time_ms);
	}
}
