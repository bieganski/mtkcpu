from nmigen import Signal, Elaboratable, Module
from mtkcpu.utils.isa import Funct3, InstrType
from mtkcpu.utils.common import matcher


class LogicUnit(Elaboratable):
    def __init__(self):
        self.src1 = Signal(32, name="logic_src1")
        self.src2 = Signal(32, name="logic_src2")
        self.res = Signal(32, name="logic_res")
        self.funct3 = Signal(Funct3)

    def elaborate(self, platform):
        m = Module()
        with m.Switch(self.funct3):
            with m.Case(Funct3.OR):
                m.d.comb += self.res.eq(self.src1 | self.src2)
            with m.Case(Funct3.AND):
                m.d.comb += self.res.eq(self.src1 & self.src2)
            with m.Case(Funct3.XOR):
                m.d.comb += self.res.eq(self.src1 ^ self.src2)
        return m


match_logic_unit = matcher(
    [
        (InstrType.ALU, Funct3.OR, 0b0000000),
        (InstrType.ALU, Funct3.AND, 0b0000000),
        (InstrType.ALU, Funct3.XOR, 0b0000000),
        (InstrType.OP_IMM, Funct3.XOR),
        (InstrType.OP_IMM, Funct3.OR),
        (InstrType.OP_IMM, Funct3.AND),
    ]
)
