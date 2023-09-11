set verbose on
set arch riscv:rv32
set riscv use-compressed-breakpoints no
target extended-remote localhost:3333
set mem inaccessible-by-default off
set remotetimeout 10
load
b main
run  
