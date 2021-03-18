from nmigen import *

from isa import Funct3, Funct7, InstrType
from functools import reduce
from operator import or_

class ShifterUnit(Elaboratable):
    def __init__(self):
        self.src1 = Signal(32, name="bbb")
        self.src1signed = Signal(signed(32))
        self.shift = Signal(5, name="ccc") # 5 lowest imm bits
        self.res = Signal(32, name="aaa")
        self.funct3 = Signal(Funct3, name="aba")
        

    def elaborate(self, platform):
        # TODO get rid of S{L/R/A}I (because they are the same as S{L/R/A})
        m = Module()
        with m.Switch(self.funct3):
            with m.Case(Funct3.SLL): # | Funct3.SLLI
                m.d.comb += self.res.eq(self.src1 << self.shift)
            with m.Case(Funct3.SRL): # | Funct3.SRLI
                m.d.comb += self.res.eq(self.src1 >> self.shift)
            with m.Case(Funct3.SRA): # | Funct3.SRAI
                m.d.comb += [
                    self.src1signed.eq(self.src1),
                    self.res.eq(self.src1signed >> self.shift), # TODO check me
                ]
        return m


from common import matcher

match_shifter_unit = matcher([
    (InstrType.OP_IMM,  Funct3.SLLI,    Funct7.SLLI),
    (InstrType.OP_IMM,  Funct3.SRLI,    Funct7.SRLI),
    (InstrType.OP_IMM,  Funct3.SRAI,    Funct7.SRAI),
    (InstrType.ALU,     Funct3.SRA,    Funct7.SRA),
    (InstrType.ALU,     Funct3.SRL,    Funct7.SRL),
    (InstrType.ALU,     Funct3.SLL,    Funct7.SLL),
])