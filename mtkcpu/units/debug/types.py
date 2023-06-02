from dataclasses import dataclass
from typing import Annotated, Sequence, Tuple, List, Type
from enum import IntEnum

from amaranth.lib import data, enum
from amaranth import unsigned

class DMSTATUS_Layout(data.Struct):
    version : unsigned(4)
    confstrptrvalid : unsigned(1)
    hasresethaltreq : unsigned(1)
    authbusy : unsigned(1)
    authenticated : unsigned(1)
    anyhalted : unsigned(1)
    allhalted : unsigned(1)
    anyrunning : unsigned(1)
    allrunning : unsigned(1)
    anyunavail : unsigned(1)
    allunavail : unsigned(1)
    anynonexistent : unsigned(1)
    allnonexistent : unsigned(1)
    anyresumeack : unsigned(1)
    allresumeack : unsigned(1)
    anyhavereset : unsigned(1)
    allhavereset : unsigned(1)
    _zero0 : unsigned(2)
    impebreak : unsigned(1)
    _zero1 : unsigned(9)

class DMCONTROL_Layout(data.Struct):
    dmactive : unsigned(1)
    ndmreset : unsigned(1)
    clrresethaltreq : unsigned(1)
    setresethaltreq : unsigned(1)
    _zero1 : unsigned(2)
    hartselhi : unsigned(10)
    hartsello : unsigned(10)
    hasel : unsigned(1)
    _zero2 : unsigned(1)
    ackhavereset : unsigned(1)
    hartreset : unsigned(1)
    resumereq : unsigned(1)
    haltreq : unsigned( 1)

class HARTINFO_Layout(data.Struct):
    dataaddr : unsigned(12)
    datasize : unsigned(4)
    dataaccess : unsigned(1)
    _zero1 : unsigned(3)
    nscratch : unsigned(4)
    _zero2 : unsigned(8)

class ABSTRACTCS_Layout(data.Struct):
    class CMDERR(enum.IntEnum, shape=unsigned(3)):
        """
        RV_DBG_SPECS 1.0; 3.15.6 Abstract Control and Status (abstractcs, at 0x16)
        """
        NO_ERR = 0
        BUSY = 1 # An abstract command was executing while command, abstractcs, or abstractauto was written, or when one of the data or progbuf registers was read or written. 
        NOT_SUPPORTED = 2 # 3.12.6: The requested command is not supported, regardless of whether the hart is running or not.
        EXCEPTION = 3 # An exception occurred while executing the command.
        HALT_OR_RESUME = 4 # The abstract command couldn’t execute because the hart wasn’t in the required state (running/halted), or unavailable.
        BUS_ERROR = 5
        OTHER = 7


    datacount : unsigned(4)
    _zero1 : unsigned(4)
    cmderr : CMDERR
    _zero2 : unsigned(1)
    busy : unsigned(1)
    _zero3 : unsigned(11)
    progbufsize : unsigned(5)
    _zero4 : unsigned(3)


class COMMAND_Layout(data.Struct):
    class AbstractCommandCmdtype(enum.IntEnum, shape=unsigned(8)):
        AccessRegister = 0x0  # the only one required by specs to be (at least partially) implemented.
        Not_Implemented_QuickAccess = 0x1
        Not_Implemented_AccessMemory = 0x2
    control : unsigned(24)
    cmdtype : AbstractCommandCmdtype

class ABSTRACTAUTO_Layout(data.Struct):
    autoexecdata : unsigned(12)
    _zero : unsigned(4)
    autoexecprogbuf : unsigned(16)


def flat_layout_factory(size: int):
    return data.StructLayout({
        "value": unsigned(size),
    })


class AccessRegisterLayout(data.Struct):
    class AARSIZE(enum.IntEnum, shape=unsigned(3)):
        NOT_SET = 0
        BIT32   = 2
        BIT64   = 3
        BIT128  = 4
    regno : unsigned(16)
    write : unsigned(1)
    transfer : unsigned(1)
    postexec : unsigned(1)
    zero1_ : unsigned(1)
    aarsize : AARSIZE
    zero2_ : unsigned(1)


DMI_COMMAND_reg_kinds = {
    COMMAND_Layout.AbstractCommandCmdtype.AccessRegister: AccessRegisterLayout,
    # TODO - for now there are only implemented ones.
}

class DMIOp(enum.IntEnum, shape=unsigned(2)):
    NOP     = 0
    READ    = 1
    WRITE   = 2


# 6.1.2: JTAG TAPs used as a DTM must have an IR of at least 5 bits.
JTAG_IR_WIDTH = 5

class JtagIR(enum.IntEnum, shape=unsigned(JTAG_IR_WIDTH)):
    BYPASS      = 0x00
    IDCODE      = 0x01
    DTMCS       = 0x10
    DMI         = 0x11

# Default value for read-only IR
class JtagIRValue(IntEnum):
    # Pretend to be Spike for now.
    # TODO - when core is stable enough, change it to some unique value.
    IDCODE      = 0x10e31913
    DM_VERSION  = 0x1 # 0x1 stands for '0.13 Debug Spec'
    DM_ABITS    = 7 # RVDS 0.13.2, chapter 3.1: "The DMI uses between 7 and 32 address bits."

class DMISTAT(IntEnum):
    NO_ERR                              = 0
    OP_FAILED                           = 2
    OP_INTERRUPTED_WHILE_IN_PROGRESS    = 3    

@dataclass
class IR_DTMCS_Layout(data.Struct):
    version : unsigned(4)
    abits : unsigned(6)
    dmistat : unsigned(2)
    idle : unsigned(3)
    _zero0 : unsigned(1)
    dmireset : unsigned(1)
    dmihardreset : unsigned(1)
    _zero1 : unsigned(1)

class DMIReg(enum.IntEnum, shape=unsigned(JtagIRValue.DM_ABITS)):
    _UNDEFINED    = 0x0
    DMSTATUS     = 0x11
    DMCONTROL    = 0x10
    HARTINFO     = 0x12
    ABSTRACTCS   = 0x16
    COMMAND      = 0x17
    SBCS         = 0x38
    DATA0        = 0x4
    DATA1        = 0x5
    PROGBUF0     = 0x20
    PROGBUF1     = 0x21
    PROGBUF2     = 0x22
    ABSTRACTAUTO = 0x18


class IR_DMI_Layout(data.Struct):
    op : DMIOp
    data : unsigned(32)
    address : DMIReg

JTAG_IR_regs = {
    JtagIR.IDCODE: flat_layout_factory(32),
    JtagIR.DTMCS: IR_DTMCS_Layout,
    JtagIR.DMI: IR_DMI_Layout,
}

DMI_reg_kinds = {
    DMIReg.DMSTATUS: DMSTATUS_Layout,
    DMIReg.DMCONTROL: DMCONTROL_Layout,
    DMIReg.HARTINFO: HARTINFO_Layout,
    DMIReg.ABSTRACTCS: ABSTRACTCS_Layout,
    DMIReg.COMMAND: COMMAND_Layout,
    DMIReg.ABSTRACTAUTO: ABSTRACTAUTO_Layout,

    DMIReg.DATA0: flat_layout_factory(32),
    DMIReg.DATA1: flat_layout_factory(32),
    DMIReg.PROGBUF0: flat_layout_factory(32),
    DMIReg.PROGBUF1: flat_layout_factory(32),
    DMIReg.PROGBUF2: flat_layout_factory(32),
}