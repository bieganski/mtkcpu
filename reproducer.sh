#!/bin/bash

python3 mtkcpu/tests/test_debug_unit.py 2>/dev/null | grep -q "False 1" ; echo $?
