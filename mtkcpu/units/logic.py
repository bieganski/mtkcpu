from nmigen import *

from isa import Funct3, InstrType
from functools import reduce
from operator import or_

class LogicUnit(Elaboratable):
    def __init__(self):
        self.src1 = Signal(32)
        self.src2 = Signal(32)
        self.res = Signal(32)
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


from common import matcher

match_logic_unit = matcher([
    (InstrType.ALU, Funct3.OR),
    (InstrType.ALU, Funct3.AND),
    (InstrType.ALU, Funct3.XOR),
])