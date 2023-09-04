from pathlib import Path
import logging

linker_script_template = """
OUTPUT_ARCH( "riscv" )

ENTRY( start )

PHDRS
{
  ram_h PT_LOAD;
}

MEMORY
{
  ram  (wxai! r) : ORIGIN = %(template_mem_start_addr)s, LENGTH = %(template_mem_size_kb)dK
}

SECTIONS {
        . = %(template_mem_start_addr)s;
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
"""

def write_linker_script(out_path : Path, mem_addr : int, mem_size_kb: int = 1):
	logging.info(f"writing linker script to {out_path}, addr: {hex(mem_addr)} of size {mem_size_kb} kb..")
	linker_script_content = linker_script_template % {
		'template_mem_start_addr': hex(mem_addr),
		'template_mem_size_kb': mem_size_kb
	}
	out_path.open("w").write(linker_script_content)
	logging.info(f"OK, linker script written to {out_path} file!")
