from nmigen import *

from isa import Funct3, InstrType
from functools import reduce
from operator import or_

class CompareUnit(Elaboratable):
    def __init__(self):
        # Input signals.
        self.src1 = Signal(signed(32), name="compare_src1")
        self.src2 = Signal(signed(32), name="compare_src2")
        self.funct3 = Signal(Funct3)

        # Output signals.
        self.condition_met  = Signal(name="compare_condition_met")
        

    def elaborate(self, platform):
        m = Module()
        with m.Switch(self.funct3):
            with m.Case(Funct3.SLT):
                m.d.comb += self.condition_met.eq(self.src1 < self.src2)
            with m.Case(Funct3.SLTU):
                m.d.comb += self.condition_met.eq(self.src1.as_unsigned() < self.src2.as_unsigned())
        return m


from common import matcher

match_compare_unit = matcher([
    (InstrType.ALU, Funct3.SLT),
    (InstrType.ALU, Funct3.SLTU),

    (InstrType.OP_IMM, Funct3.SLT),
    (InstrType.OP_IMM, Funct3.SLTU),
])