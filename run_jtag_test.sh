#!/bin/bash

pkill -f openocd
pkill -f riscv-none-embed-gdb

# poetry run pytest mtkcpu/tests/test_jtag.py --verbose --capture=no
python3 mtkcpu/tests/test_jtag.py
stty sane
