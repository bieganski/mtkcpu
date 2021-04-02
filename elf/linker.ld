SECTIONS {
	. = 0x1000;
	start : { *(start) }
	.text : { *(.text*) }
	.rodata : { *(.rodata*) }
	.data : { *(.data* .bss*) }
	_bss_end = .;
	ASSERT (_bss_end < 0x0a000, "Too much code!")
}
