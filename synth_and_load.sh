#!/bin/bash

set -x
set -eu
GIT_ROOT=`git rev-parse --show-toplevel`
# pip3 install $GIT_ROOT

elf_path=$GIT_ROOT/elf/unit/gpio_led.elf
$GIT_ROOT/mtkcpu/cli/top.py --build --elf $elf_path --program

REPORT=build/top.tim

grep "Max frequency for clock" $REPORT
grep -A 16 "Info: Device utilisation" $REPORT
