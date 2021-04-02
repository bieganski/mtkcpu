#!/bin/bash

set -e
set -u

DIRNAME=xpack-riscv-none-embed-gcc-8.3.0-2.3

if [ -d $DIRNAME ]; then
	echo "=== $DIRNAME dir already exists, skipping toolchain installation..."
else
	wget https://github.com/xpack-dev-tools/riscv-none-embed-gcc-xpack/releases/download/v8.3.0-2.3/xpack-riscv-none-embed-gcc-8.3.0-2.3-linux-x64.tar.gz

	tar -xzvf xpack-riscv-none-embed-gcc-8.3.0-2.3-linux-x64.tar.gz
fi

DIRNAME=`realpath $DIRNAME`

echo "=== installation complete, please run following:"

echo "export PATH=\$PATH:$DIRNAME/bin"

