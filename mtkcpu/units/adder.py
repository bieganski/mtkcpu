from nmigen import Signal, Elaboratable, Module, Cat, Mux
from mtkcpu.utils.common import matcher
from mtkcpu.utils.isa import Funct3, Funct7, InstrType


class AdderUnit(Elaboratable):
    def __init__(self):
        self.sub = Signal()  # add or sub
        self.src1 = Signal(32, name="adder_src1")
        self.src2 = Signal(32, name="adder_src2")
        self.res = Signal(32, name="adder_res")

        self.overflow = Signal(name="adder_overflow")
        self.carry = Signal(name="adder_carry")

    def elaborate(self, platform):
        m = Module()

        # neat way of setting carry flag
        res_and_carry = Cat(self.res, self.carry)

        m.d.comb += res_and_carry.eq(
            Mux(self.sub, self.src1 - self.src2, self.src1 + self.src2)
        )

        with m.If(self.sub):
            with m.If(
                (self.src1[-1] != self.src2[-1])
                & (self.src1[-1] != self.res[-1])
            ):
                m.d.comb += self.overflow.eq(1)
        with m.Else():
            # add
            with m.If(
                (self.src1[-1] == self.src2[-1])
                & (self.src1[-1] != self.res[-1])
            ):
                m.d.comb += self.overflow.eq(1)

        return m


match_adder_unit = matcher(
    [
        (InstrType.ALU, Funct3.ADD, Funct7.ADD),
        (InstrType.ALU, Funct3.SUB, Funct7.SUB),
        (InstrType.OP_IMM, Funct3.ADD),
        (InstrType.OP_IMM, Funct3.SUB),
    ]
)
