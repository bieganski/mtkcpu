from nmigen import *

from isa import Funct3, Funct7, InstrType
from functools import reduce
from operator import or_

class ShifterUnit(Elaboratable):
    def __init__(self):
        self.src1 = Signal(32, name="bbb")
        self.shift = Signal(5, name="ccc") # 5 lowest imm bits
        self.res = Signal(32, name="aaa")
        self.funct3 = Signal(Funct3, name="aba")
        

    def elaborate(self, platform):
        m = Module()
        with m.Switch(self.funct3):
            with m.Case(Funct3.SLL): # | Funct3.SLLI
                m.d.comb += self.res.eq(self.src1 << self.shift)
            with m.Case(Funct3.SRL): # | Funct3.SRLI
                m.d.comb += self.res.eq(self.src1 >> self.shift)
            # with m.Case(Funct3.SRA): # | Funct3.SRAI
            #     pass # TODO
        return m


from common import matcher

match_shifter_unit = matcher([
    (InstrType.OP_IMM,  Funct3.SLL,  ), #   Funct7.SLLI),
    (InstrType.OP_IMM,  Funct3.SRL,  ), #   Funct7.SRLI),
    (InstrType.OP_IMM,  Funct3.SRA,  ), #   Funct7.SRAI),
    (InstrType.ALU,     Funct3.SRA,  ), #    Funct3.SRA),
    (InstrType.ALU,     Funct3.SRL,  ), #    Funct3.SRL),
    (InstrType.ALU,     Funct3.SLL,  ), #    Funct7.SLL),
])