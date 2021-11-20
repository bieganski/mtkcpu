    .section .init
    .globl start
    .type start,@function
/* 
Following file assumes that linker set some variables:
	* _start - address of first instruction to be executed
	*  __global_pointer ??
	* _init ??

	* __bss_start
	* _end (why not bss_end?)

*/
start:
	la sp, _sp # set stack pointer, according to linker-script defined value.
	# call __libc_init_array
	call main
mainDone:
    j mainDone
_init:
    ret


/*
_start:
#ifdef USE_GP
.option push
.option norelax
	la gp, __global_pointer$
.option pop
#endif
	la sp, _sp

	// Load data section
	la a0, _data_lma
	la a1, _data
	la a2, _edata
	bgeu a1, a2, 2f
1:
	lw t0, (a0)
	sw t0, (a1)
	addi a0, a0, 4
	addi a1, a1, 4
	bltu a1, a2, 1b
2:

	// Clear bss section
	la a0, __bss_start
	la a1, _end
	bgeu a0, a1, 2f
1:
	sw zero, (a0)
	addi a0, a0, 4
	bltu a0, a1, 1b
2:

	call __libc_init_array
	call main
mainDone:
    j mainDone

	.globl _init
_init:
    ret
*/