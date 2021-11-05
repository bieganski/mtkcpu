#!/bin/bash

# set -x
set -eu
GIT_ROOT=`git rev-parse --show-toplevel`
pip3 install $GIT_ROOT
$GIT_ROOT/mtkcpu/cli/top.py

REPORT=build/top.tim

grep "Max frequency for clock" $REPORT
grep -A 16 "Info: Device utilisation" $REPORT
