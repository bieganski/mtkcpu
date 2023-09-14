# Following file comes (with some changes) from minerva, A 32-bit RISC-V soft processor
# https://github.com/minerva-cpu/minerva

from enum import IntEnum, unique
# TODO move me to proper location
from typing import List, Tuple


def get_layout_field_offset(layout : List[Tuple[str, int]], field : str):
    offset = 0
    for name, width, *_ in layout:
        if name != field:
            offset += width
        else:
            return offset
    raise ValueError(f"field {field} not found among layout {layout}!")

@unique
class CSRNonStandardIndex(IntEnum):
    # RiscV privileged ISA defines CSR address range 0x7C0-0x7FF as 'Non-standard read/write'
    MTIME = 0x7c0
    MTIMECMP = 0x7c1

@unique
class PrivModeBits(IntEnum):
    # Priv. ISA v1.10 - table 1.1.
    USER = 0b00
    SUPERVISOR = 0b01
    MACHINE = 0b11

@unique
class CSRIndex(IntEnum):
    MVENDORID   = 0xF11
    MARCHID     = 0xF12
    MIMPID      = 0xF13
    MHARTID     = 0xF14
    MSTATUS     = 0x300
    MISA        = 0x301
    MEDELEG     = 0x302
    MIDELEG     = 0x303
    MIE         = 0x304
    MTVEC       = 0x305
    MCOUTEREN   = 0x306
    MSCRATCH    = 0x340
    MEPC        = 0x341
    MCAUSE      = 0x342
    MTVAL       = 0x343
    MIP         = 0x344
    # µarch specific
    IRQ_MASK    = 0x330
    IRQ_PENDING = 0x360
    # trigger module
    TSELECT     = 0x7a0
    TDATA1      = 0x7a1
    TDATA2      = 0x7a2
    TDATA3      = 0x7a3
    TINFO       = 0x7a4
    MCONTEXT    = 0x7a8
    # debug module
    DCSR        = 0x7b0
    DPC         = 0x7b1

    # supervisor
    SATP        = 0x180

@unique
class TrapCause(IntEnum):
    FETCH_MISALIGNED     = 0
    FETCH_ACCESS_FAULT   = 1
    ILLEGAL_INSTRUCTION  = 2
    BREAKPOINT           = 3
    LOAD_MISALIGNED      = 4
    LOAD_ACCESS_FAULT    = 5
    STORE_MISALIGNED     = 6
    STORE_ACCESS_FAULT   = 7
    ECALL_FROM_U         = 8
    ECALL_FROM_S         = 9
    ECALL_FROM_M         = 11
    FETCH_PAGE_FAULT     = 12
    LOAD_PAGE_FAULT      = 13
    STORE_PAGE_FAULT     = 15

@unique
class IrqCause(IntEnum):
    U_SOFTWARE_INTERRUPT = 0
    S_SOFTWARE_INTERRUPT = 1
    M_SOFTWARE_INTERRUPT = 3
    U_TIMER_INTERRUPT    = 4
    S_TIMER_INTERRUPT    = 5
    M_TIMER_INTERRUPT    = 7
    U_EXTERNAL_INTERRUPT = 8
    S_EXTERNAL_INTERRUPT = 9
    M_EXTERNAL_INTERRUPT = 11


# CSR layouts

flat_layout = [
    ("value", 32),
]


class MisaExtensionBit(IntEnum):
    INTEGER_BASE_ISA = 1 << 8
    MULDIV = 1 << 12

class MisaRXL(IntEnum):
    RV32 = 1
    RV64 = 2

class MtvecModeBits(IntEnum):
    DIRECT = 0 # All exceptions set pc to BASE.
    VECTORED = 1 # Asynchronous interrupts set pc to BASE+4×cause.

misa_layout = [
    ("extensions", 26),
    ("zero",        4),
    ("mxl",         2),
]

mstatus_layout = [
    ("uie",   1), # User Interrupt Enable
    ("sie",   1), # Supervisor Interrupt Enable
    ("zero0", 1),
    ("mie",   1), # Machine Interrupt Enable
    ("upie",  1), # User Previous Interrupt Enable
    ("spie",  1), # Supervisor Previous Interrupt Enable
    ("zero1", 1),
    ("mpie",  1), # Machine Previous Interrupt Enable
    ("spp",   1), # Supervisor Previous Privilege
    ("zero2", 2),
    ("mpp",   2), # Machine Previous Privilege
    ("fs",    2), # FPU Status
    ("xs",    2), # user-mode eXtensions Status
    ("mprv",  1), # Modify PRiVilege
    ("sum",   1), # Supervisor User Memory access
    ("mxr",   1), # Make eXecutable Readable
    ("tvm",   1), # Trap Virtual Memory
    ("tw",    1), # Timeout Wait
    ("tsr",   1), # Trap SRET
    ("zero3", 8),
    ("sd",    1), # State Dirty (set if XS or FS are set to dirty)
]

mtvec_layout = [
    ("mode",  2),
    ("base", 30),
]

mip_layout = [
    ("usip",   1),
    ("ssip",   1),
    ("zero0",  1),
    ("msip",   1),
    ("utip",   1),
    ("stip",   1),
    ("zero1",  1),
    ("mtip",   1),
    ("ueip",   1),
    ("seip",   1),
    ("zero2",  1),
    ("meip",   1),
    ("zero3", 20),
]


mie_layout = [
    ("usie",   1),
    ("ssie",   1),
    ("zero0",  1),
    ("msie",   1),
    ("utie",   1),
    ("stie",   1),
    ("zero1",  1),
    ("mtie",   1),
    ("ueie",   1),
    ("seie",   1),
    ("zero2",  1),
    ("meie",   1),
    ("zero3", 20),
]


mcause_layout = [
    ("ecode",    31),
    ("interrupt", 1),
]


dcsr_layout = [
    ("prv",        2),
    ("step",       1),
    ("nmip",       1),
    ("mprven",     1),
    ("v",          1),
    ("cause",      3),
    ("stoptime",   1),
    ("stopcount",  1),
    ("stepie",     1),
    ("ebreaku",    1),
    ("ebreaks",    1),
    ("zero1",      1),
    ("ebreakm",    1),
    ("ebreakvu",   1),
    ("ebreakvs",   1),
    ("zero2",     10),
    ("debugver",   4), 
]


tdata1_layout = [
    ("data",  27),
    ("dmode",  1),
    ("type",   4),
]


satp_layout = [
    ("ppn", 22),
    ("asid", 9),
    ("mode", 1),
]

pte_layout = [
    ("v", 1),
    ("r", 1),
    ("w", 1),
    ("x", 1),
    ("u", 1),
    ("g", 1),
    ("a", 1),
    ("d", 1),
    ("rsw", 2),
    ("ppn0", 10),
    ("ppn1", 12),
]

virt_addr_layout = [
    ("page_offset", 12),
    ("vpn0", 10),
    ("vpn1", 10),
]