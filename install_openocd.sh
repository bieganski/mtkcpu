#!/bin/bash

set -eux

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

cd $SCRIPT_DIR

DIRNAME=openocd_riscv

if [ -d $DIRNAME ]; then
	echo "=== $DIRNAME dir already exists, skipping openocd install..."
else
	git clone https://github.com/SpinalHDL/openocd_riscv
fi

cd openocd_riscv

# below instructions come from README.md of 'openocd_riscv' repository.\
sudo apt-get install libtool automake libusb-1.0.0-dev texinfo libusb-dev libyaml-dev pkg-config
./bootstrap
./configure --enable-ftdi --enable-dummy
make
#sudo make install

echo "=== installation complete, please run following:"

echo "export PATH=\$PATH:$DIRNAME/bin"

