#!/bin/bash

poetry run pytest mtkcpu/tests/test_jtag.py --verbose --capture=no
stty sane
