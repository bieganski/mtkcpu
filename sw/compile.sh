#!/bin/bash

set -e
# set -u

function log {
	echo "==== $@"
}

function green {
	red=`tput setaf 1`
	green=`tput setaf 2`
	reset=`tput sgr0`
	echo -ne "${green}$@${reset}"
}


function red {
	red=`tput setaf 1`
	green=`tput setaf 2`
	reset=`tput sgr0`
	echo -ne "${red}$@${reset}"
}





LINKER=linker.ld
TOOL=riscv-none-embed
OPT=-Os
ARCH=rv32i
SRC="$1"
DEFAULT_SRC="example.S"

if [ "$1" == "" ]; then
	echo -ne "=== no source filename param specified, chosing default ("
	green $DEFAULT_SRC
	echo ")..."
	SRC=$DEFAULT_SRC
fi

ELF=${SRC%.*}.elf

$TOOL-gcc $OPT -march=$ARCH -nostartfiles -T$LINKER $SRC -o $ELF

echo -ne "compilation successfull, "
green $ELF 
echo " file created..."

$TOOL-objdump --disassembler-options=no-aliases -M numeric -d $ELF
