from nmigen import *

class AdderUnit(Elaboratable):
    def __init__(self):
        self.sub = Signal() # add or sub
        self.src1 = Signal(32)
        self.src2 = Signal(32)
        self.res = Signal(32)

    def elaborate(self, platform):
        m = Module()

        m.d.comb += self.res.eq(
            Mux(self.sub,
                self.src1 - self.src2,
                self.src1 + self.src2
        ))

        return m

from common import matcher
from isa import Funct3, Funct7, InstrType

match_adder_unit = matcher([
    (InstrType.ALU, Funct3.ADD, Funct7.ADD),
    (InstrType.ALU, Funct3.SUB, Funct7.SUB),
])