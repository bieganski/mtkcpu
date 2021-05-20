from nmigen import Elaboratable, Signal, Module
from mtkcpu.utils.isa import Funct3, InstrType
from mtkcpu.utils.common import matcher


class CompareUnit(Elaboratable):
    def __init__(self):
        # Input signals.
        self.funct3 = Signal(Funct3)
        self.zero = Signal()
        self.negative = Signal(name="cmp_negative")

        # meawhile, Adder Unit performs 'src1' - 'src2' and outputs carry and overflow signals.
        self.carry = Signal(name="cmp_carry")
        self.overflow = Signal(name="cmp_overflow")

        # Output signals.
        self.condition_met = Signal(name="compare_condition_met")

    def elaborate(self, platform):
        m = Module()
        with m.Switch(self.funct3):
            with m.Case(Funct3.SLT):
                m.d.comb += self.condition_met.eq(
                    self.negative | self.overflow
                )
            with m.Case(Funct3.SLTU):
                m.d.comb += self.condition_met.eq(self.carry)

            with m.Case(Funct3.BEQ):
                m.d.comb += self.condition_met.eq(self.zero)
            with m.Case(Funct3.BNE):
                m.d.comb += self.condition_met.eq(~self.zero)
            with m.Case(Funct3.BLT):
                m.d.comb += self.condition_met.eq(
                    self.negative ^ self.overflow
                )
            with m.Case(Funct3.BGE):
                m.d.comb += self.condition_met.eq(
                    ~(self.negative ^ self.overflow)
                )
            with m.Case(Funct3.BLTU):
                m.d.comb += self.condition_met.eq(self.carry)
            with m.Case(Funct3.BGEU):
                m.d.comb += self.condition_met.eq(~self.carry)
        return m


match_compare_unit = matcher(
    [
        (InstrType.ALU, Funct3.SLT),
        (InstrType.ALU, Funct3.SLTU),
        (InstrType.OP_IMM, Funct3.SLT),
        (InstrType.OP_IMM, Funct3.SLTU),
    ]
)
