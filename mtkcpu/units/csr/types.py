from dataclasses import dataclass
from enum import IntEnum

from amaranth.lib import data, enum
from amaranth import unsigned


class MISA_Layout(data.Struct):
    extensions: unsigned(6)
    zero:       unsigned(4)
    mxl:        unsigned(2)

class MSTATUS_Layout(data.Struct):
    uie:    unsigned(1) # User Interrupt Enable
    sie:    unsigned(1) # Supervisor Interrupt Enable
    zero0:  unsigned(1)
    mie:    unsigned(1) # Machine Interrupt Enable
    upie:   unsigned(1) # User Previous Interrupt Enable
    spie:   unsigned(1) # Supervisor Previous Interrupt Enable
    zero1:  unsigned(1)
    mpie:   unsigned(1) # Machine Previous Interrupt Enable
    spp:    unsigned(1) # Supervisor Previous Privilege
    zero2:  unsigned(2)
    mpp:    unsigned(2) # Machine Previous Privilege
    fs:     unsigned(2) # FPU Status
    xs:     unsigned(2) # user-mode eXtensions Status
    mprv:   unsigned(1) # Modify PRiVilege
    sum:    unsigned(1) # Supervisor User Memory access
    mxr:    unsigned(1) # Make eXecutable Readable
    tvm:    unsigned(1) # Trap Virtual Memory
    tw:     unsigned(1) # Timeout Wait
    tsr:    unsigned(1) # Trap SRET
    zero3:  unsigned(8)
    sd:     unsigned(1) # State Dirty (set if XS or FS are set to dirty)

class MTVEC_Layout(data.Struct):
    mode:   unsigned(2)
    base:   unsigned(30)

class MIP_Layout(data.Struct):
    usip:   unsigned(1)
    ssip:   unsigned(1)
    zero0:  unsigned(1)
    msip:   unsigned(1)
    utip:   unsigned(1)
    stip:   unsigned(1)
    zero1:  unsigned(1)
    mtip:   unsigned(1)
    ueip:   unsigned(1)
    seip:   unsigned(1)
    zero2:  unsigned(1)
    meip:   unsigned(1)
    zero3:  unsigned(20)

class MIE_Layout(data.Struct):
    usie:   unsigned(1)
    ssie:   unsigned(1)
    zero0:  unsigned(1)
    msie:   unsigned(1)
    utie:   unsigned(1)
    stie:   unsigned(1)
    zero1:  unsigned(1)
    mtie:   unsigned(1)
    ueie:   unsigned(1)
    seie:   unsigned(1)
    zero2:  unsigned(1)
    meie:   unsigned(1)
    zero3:  unsigned(20)

class MCAUSE_Layout(data.Struct):
    ecode:      unsigned(31)
    interrupt:  unsigned(1)

class DCSR_Layout(data.Struct):
    prv:        unsigned(2)
    step:       unsigned(1)
    nmip:       unsigned(1)
    mprven:     unsigned(1)
    v:          unsigned(1)
    cause:      unsigned(3)
    stoptime:   unsigned(1)
    stopcount:  unsigned(1)
    stepie:     unsigned(1)
    ebreaku:    unsigned(1)
    ebreaks:    unsigned(1)
    zero1:      unsigned(1)
    ebreakm:    unsigned(1)
    ebreakvu:   unsigned(1)
    ebreakvs:   unsigned(1)
    zero2:      unsigned(10)
    debugver:   unsigned(4)

class SATP_Layout(data.Struct):
    ppn:    unsigned(22)
    asid:   unsigned(9)
    mode:   unsigned(1)


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
