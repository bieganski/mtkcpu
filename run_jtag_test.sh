#!/bin/bash

poetry run pytest mtkcpu/tests/test_jtag.py --verbose --capture=no;
python3 -c "from beepy import beep; beep()"
