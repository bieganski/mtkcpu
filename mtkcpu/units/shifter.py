from amaranth import Signal, Elaboratable, Module, signed
from mtkcpu.cpu.isa import Funct3, Funct7, InstrType
from mtkcpu.utils.common import matcher


class ShifterUnit(Elaboratable):
    def __init__(self):
        self.src1 = Signal(32, name="shifter_src1")
        self.src1signed = Signal(signed(32))
        self.shift = Signal(5, name="shifter_shift")  # 5 lowest imm bits
        self.res = Signal(32, name="shifter_res")
        self.funct3 = Signal(Funct3)
        self.funct7 = Signal(Funct7)

    def elaborate(self, platform):
        assert Funct3.SLLI == Funct3.SLL
        assert Funct3.SRL == Funct3.SRLI
        assert Funct3.SRA == Funct3.SRAI
        m = Module()
        with m.Switch(self.funct3):
            with m.Case(Funct3.SLL):
                m.d.comb += self.res.eq(self.src1 << self.shift)
            with m.Case(Funct3.SRL):
                assert Funct3.SRL == Funct3.SRA
                assert Funct7.SRL != Funct7.SRA

                with m.If(self.funct7 == Funct7.SRL):
                    m.d.comb += self.res.eq(self.src1 >> self.shift)
                with m.Elif(self.funct7 == Funct7.SRA):
                    m.d.comb += [
                        self.src1signed.eq(self.src1),
                        self.res.eq(self.src1signed >> self.shift),
                    ]
        return m


match_shifter_unit = matcher(
    [
        (InstrType.OP_IMM, Funct3.SLLI, Funct7.SLLI),
        (InstrType.OP_IMM, Funct3.SRLI, Funct7.SRLI),
        (InstrType.OP_IMM, Funct3.SRAI, Funct7.SRAI),
        (InstrType.ALU, Funct3.SRA, Funct7.SRA),
        (InstrType.ALU, Funct3.SRL, Funct7.SRL),
        (InstrType.ALU, Funct3.SLL, Funct7.SLL),
    ]
)
