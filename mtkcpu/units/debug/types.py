from dataclasses import dataclass
from typing import Annotated, Sequence, Tuple, List, Type
from enum import IntEnum

from amaranth.lib import data
from amaranth import unsigned

@dataclass
class NamedOrderedLayout:
    """
    Generic class to be overloaded, not instantiated directly.

    Represents a CPU register layout, split into named fields.

    All fields must be type annotated as Annotated[int, x], where x is <num_bits> that the field occupies.
    Fields are encoded/decoded in an order that they were defined.

    'Annotated' type allows for adding any metadata to types, as described here: https://stackoverflow.com/a/67146944.
    """

    @classmethod
    def _fetch_fields_ordered(cls) -> Sequence[Tuple[Type, str, int]]:
        """
        Usually type returned will be int or IntEnum.
        """
        fields_ordered = cls.__dataclass_fields__
        for field_name, field in fields_ordered.items():
            if not hasattr(field.type, "__metadata__"):
                raise ValueError(f"For proper struct.pack invocation, size of each field must be known! Please use Annotated type with proper metadata for field '{field_name}'")
            type = field.type
            num_bytes = type.__metadata__[0]
            yield type, field_name, num_bytes
    
    @classmethod
    def from_int(cls, value: int) -> "NamedOrderedLayout":
        args = []
        for type, _, size in cls._fetch_fields_ordered():
            typed_val = type(value & (2 ** size - 1))
            args.append(typed_val)
            value = value >> size
        return cls(*args)

    @classmethod
    def width(cls, field_name: str) -> int:
        for type, name, size in cls._fetch_fields_ordered():
            if name == field_name:
                return size
        raise ValueError(f"Could not find named '{field_name}' in {cls}!")
    
    @classmethod
    def total_width(cls) -> int:
        return sum([size for _, _, size in cls._fetch_fields_ordered()])
    
    @classmethod
    def to_layout(cls) -> List[Tuple[str, int]]:
        return list([(x, y) for _, x, y in cls._fetch_fields_ordered()])

class DMIReg(IntEnum):
    DMSTATUS = 0x11
    DMCONTROL = 0x10
    HARTINFO = 0x12
    ABSTRACTCS = 0x16
    COMMAND = 0x17
    SBCS = 0x38
    DATA0 = 0x4
    DATA1 = 0x5
    PROGBUF0 = 0x20
    PROGBUF1 = 0x21
    PROGBUF2 = 0x22
    ABSTRACTAUTO = 0x18

class DMICommand(IntEnum):
    AccessRegister = 0x0  # the only one required by specs to be (at least partially) implemented.
    Not_Implemented_QuickAccess = 0x1
    Not_Implemented_AccessMemory = 0x2


@dataclass
class DMSTATUS_Layout(NamedOrderedLayout):
    version : Annotated[int, 4]
    confstrptrvalid : Annotated[int, 1]
    hasresethaltreq : Annotated[int, 1]
    authbusy : Annotated[int, 1]
    authenticated : Annotated[int, 1]
    anyhalted : Annotated[int, 1]
    allhalted : Annotated[int, 1]
    anyrunning : Annotated[int, 1]
    allrunning : Annotated[int, 1]
    anyunavail : Annotated[int, 1]
    allunavail : Annotated[int, 1]
    anynonexistent : Annotated[int, 1]
    allnonexistent : Annotated[int, 1]
    anyresumeack : Annotated[int, 1]
    allresumeack : Annotated[int, 1]
    anyhavereset : Annotated[int, 1]
    allhavereset : Annotated[int, 1]
    _zero0 : Annotated[int, 2]
    impebreak : Annotated[int, 1] # R, 1 if implicit ebreak at the end of program buffer
    _zero1 : Annotated[int, 9]

@dataclass
class DMCONTROL_Layout(NamedOrderedLayout):
    dmactive : Annotated[int, 1]
    ndmreset : Annotated[int, 1]
    clrresethaltreq : Annotated[int, 1]
    setresethaltreq : Annotated[int, 1]
    _zero1 : Annotated[int, 2]
    hartselhi : Annotated[int, 10]
    hartsello : Annotated[int, 10]
    hasel : Annotated[int, 1]
    _zero2 : Annotated[int, 1]
    ackhavereset : Annotated[int, 1]
    hartreset : Annotated[int, 1]
    resumereq : Annotated[int, 1]
    haltreq : Annotated[int,  1]

@dataclass
class HARTINFO_Layout(NamedOrderedLayout):
    dataaddr : Annotated[int, 12]
    datasize : Annotated[int, 4]
    dataaccess : Annotated[int, 1]
    _zero1 : Annotated[int, 3]
    nscratch : Annotated[int, 4]
    _zero2 : Annotated[int, 8]

@dataclass
class ABSTRACTCS_Layout(NamedOrderedLayout):
    datacount : Annotated[int, 4]
    _zero1 : Annotated[int, 4]
    cmderr : Annotated[int, 3]
    _zero2 : Annotated[int, 1]
    busy : Annotated[int, 1]
    _zero3 : Annotated[int, 11]
    progbufsize : Annotated[int, 5]
    _zero4 : Annotated[int, 3]

@dataclass
class COMMAND_Layout(NamedOrderedLayout):
    control : Annotated[int, 24]
    cmdtype : Annotated[DMICommand, 8]

@dataclass
class ABSTRACTAUTO_Layout(NamedOrderedLayout):
    autoexecdata : Annotated[int, 12]
    _zero : Annotated[int, 4]
    autoexecprogbuf : Annotated[int, 16]

@dataclass
class _flat_Layout(NamedOrderedLayout):
    value : Annotated[int, 32]

DMI_reg_kinds = {
    DMIReg.DMSTATUS: DMSTATUS_Layout.to_layout(),
    DMIReg.DMCONTROL: DMCONTROL_Layout.to_layout(),
    DMIReg.HARTINFO: HARTINFO_Layout.to_layout(),
    DMIReg.ABSTRACTCS: ABSTRACTCS_Layout.to_layout(),
    DMIReg.COMMAND: COMMAND_Layout.to_layout(),
    DMIReg.ABSTRACTAUTO: ABSTRACTAUTO_Layout.to_layout(),

    DMIReg.DATA0: _flat_Layout.to_layout(),
    DMIReg.DATA1: _flat_Layout.to_layout(),
    DMIReg.PROGBUF0: _flat_Layout.to_layout(),
    DMIReg.PROGBUF1: _flat_Layout.to_layout(),
    DMIReg.PROGBUF2: _flat_Layout.to_layout(),
}


@dataclass
class AccessRegisterLayout(NamedOrderedLayout):
    regno : Annotated[int, 16]
    write : Annotated[int, 1]
    transfer : Annotated[int, 1]
    postexec : Annotated[int, 1]
    _zero1 : Annotated[int, 1]
    aarsize : Annotated[int, 3]
    _zero2 : Annotated[int, 1]

assert AccessRegisterLayout.from_int(0x1).regno == 0x1

DMI_COMMAND_reg_kinds = {
    DMICommand.AccessRegister: AccessRegisterLayout.to_layout()
}

reg_len = lambda lst: sum(map(lambda x : x[1], lst))
assert all(map(lambda lst: 32 == reg_len(lst), DMI_reg_kinds.values()))
assert all(map(lambda lst: 24 == reg_len(lst), DMI_COMMAND_reg_kinds.values()))


class DMIOp(IntEnum):
    NOP     = 0
    READ    = 1
    WRITE   = 2


# Spike's irlen == 5
class JtagIR(IntEnum):
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


class IR_DMI_Layout(data.Struct):
    op : unsigned(2)
    data : unsigned(32)
    address : unsigned(JtagIRValue.DM_ABITS)

def flat_layout_factory(size: int):
    return data.StructLayout({
        "value": unsigned(size),
    })

JTAG_IR_regs = {
    JtagIR.IDCODE: flat_layout_factory(32),
    JtagIR.DTMCS: IR_DTMCS_Layout,
    JtagIR.DMI: IR_DMI_Layout,
}