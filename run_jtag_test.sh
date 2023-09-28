#!/bin/bash

pkill -f riscv-none-elf-gdb
pkill --signal SIGUSR1 -f openocd

# poetry run pytest mtkcpu/tests/test_jtag.py --verbose --capture=no
python3 mtkcpu/tests/test_jtag.py
stty sane
