#include "utils.h"

int main() {
	auto sleep_time_ms = 1000;
	while(true) {
		enable_green_led();
		disable_red_led();
		sleep(sleep_time_ms);
		enable_red_led();
		disable_green_led();
		sleep(sleep_time_ms);
	}
}
