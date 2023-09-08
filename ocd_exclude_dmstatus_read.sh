#!/bin/bash

set -eux

../riscv-openocd/src/openocd --debug   -f openocd_diligent  2>&1 \
	| grep -v "@11" \
	| grep -v riscv_openocd_poll \
	| grep -v riscv_poll_hart \
	| grep -v handle_target \
	| grep -v riscv_flush_registers

