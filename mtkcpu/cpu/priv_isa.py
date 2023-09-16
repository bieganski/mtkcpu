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

from amaranth.lib import data
from amaranth import unsigned

class PTE_Layout(data.Struct):
    v       : unsigned(1)
    r       : unsigned(1)
    w       : unsigned(1)
    x       : unsigned(1)
    u       : unsigned(1)
    g       : unsigned(1)
    a       : unsigned(1)
    d       : unsigned(1)
    rsw     : unsigned(2)
    ppn0    : unsigned(10)
    ppn1    : unsigned(12)

class Virt_Addr_Layout(data.Struct):
    page_offset : unsigned(12)
    vpn0        : unsigned(10)
    vpn1        : unsigned(10)