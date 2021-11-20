OUTPUT_ARCH( "riscv" )

ENTRY( start )

PHDRS
{
  ram_h PT_LOAD;
}

MEMORY
{
  ram  (wxai! r) : ORIGIN = 0x1000, LENGTH = 1K
}

SECTIONS {
	. = 0x1000;
	.init :
	{
		KEEP (*(SORT_NONE(.init)))
	} >ram AT>ram :ram_h
	start : { *(start) } >ram AT>ram :ram_h
	.text : { *(.text*) } >ram AT>ram :ram_h
	.rodata : { *(.rodata*) } >ram AT>ram :ram_h
	.data : { *(.data* .bss*) } >ram AT>ram :ram_h
	.stack  : ALIGN(16) 
	{
		. = 512; /* TODO 512 bytes for stack size is not much */
		PROVIDE( _sp = . );
	}
}
