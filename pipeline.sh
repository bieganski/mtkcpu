#!/bin/bash


set -eux


pkill -f gtkwave || true

# waits for OCD..
./run_jtag_test.sh & 
pid=$!
pushd /home/mateusz/github/openocd_riscv > /dev/null

sleep 2
timeout 8 ./src/openocd -f ./src/REMOTE_BITBANG.cfg
popd > /dev/null

kill $pid

echo "=====" 
echo "gtkwave jtag.gtkw &"
