from amaranth import Signal, Module, Elaboratable

from mtkcpu.units.csr.types import *
from mtkcpu.utils.common import CODE_START_ADDR
from mtkcpu.cpu.priv_isa import CSRIndex, CSRNonStandardIndex
from amaranth.lib import data

from abc import ABC, abstractmethod
from typing import Optional

class CSR_Write_Handler(ABC, Elaboratable):

    # 'layout' field is to be overwritten by subclasses, with more detailed ones.
    layout=data.StructLayout({"_value": unsigned(32)})

    # default 'flat' layout makes sense, but default register address could cause pain.
    @property
    @abstractmethod
    def addr(self) -> int:
        pass
    
    def __init__(self, my_reg_latch: Optional[Signal] = None):
        # -- Input signals
        # 
        # Needs to be deasserted in cycle following 'controller.cmd_finished' asserted.
        self.active = Signal()
        self.write_value = Signal(32)
        self.write_finished = Signal()

        if my_reg_latch is not None:
            self.my_reg_latch = my_reg_latch
            assert my_reg_latch.width == 32

    def as_view(self) -> data.View:
        return data.View(self.layout, self.my_reg_latch)

    def latch_whole_value_with_no_side_effect(self):
        m = Module()

        with m.If(self.active):
            m.d.sync += self.my_reg_latch.eq(self.write_value)
            m.d.comb += self.write_finished.eq(1)

        return m

    @classmethod
    def const(cls) -> int:
        return cls.layout.const(cls.reset()).as_value().value
    
    @staticmethod
    def reset() -> dict[str, int]:
        return {}
    
    def latch_partial_value_with_no_side_effect(self, fields: list[str]):
        m = Module()

        lhs = data.View(self.layout, self.my_reg_latch)
        rhs = data.View(self.layout, self.write_value)

        with m.If(self.active):
            for x in fields:
                m.d.sync += getattr(lhs, x).eq(getattr(rhs, x))
            m.d.comb += self.write_finished.eq(1)

        return m

    def no_action_at_all(self):
        return self.latch_partial_value_with_no_side_effect(fields=[])

    def elaborate(self, _):
        raise NotImplementedError()

class MISA(CSR_Write_Handler):
    layout = MISA_Layout
    addr = CSRIndex.MISA

    def elaborate(self, _):
        return self.no_action_at_all()

    def reset():
        return {
            "mxl": MisaRXL.RV32,
            "extensions": MisaExtensionBit.INTEGER_BASE_ISA,
        }

class MTVEC(CSR_Write_Handler):
    layout = MTVEC_Layout
    addr = CSRIndex.MTVEC

    def elaborate(self, _):
        return self.latch_whole_value_with_no_side_effect()

    def reset():
        return {
            "mode": MtvecModeBits.DIRECT,
            "base": (CODE_START_ADDR + 0x20) >> 2
        }


class MTVAL(CSR_Write_Handler):
    layout = MTVEC_Layout
    addr = CSRIndex.MTVAL
    
    def elaborate(self, _):
        return self.no_action_at_all()

class MEPC(CSR_Write_Handler):
    addr = CSRIndex.MEPC
    def elaborate(self, _):
        return self.latch_whole_value_with_no_side_effect()


class DPC(CSR_Write_Handler):
    addr = CSRIndex.DPC
    def elaborate(self, _):
        return self.latch_whole_value_with_no_side_effect()


class DCSR(CSR_Write_Handler):
    layout = DCSR_Layout
    addr = CSRIndex.DCSR

    def reset() -> dict[str, int]:
        return {
            # For valid (prv, v) combination, refer to Debug Specs 1.0, table 4.6.
            "prv": 3,
            "v": 0,
            # From Debug Specs 1.0:
            # 4 - Debug support exists as it is described in this document.
            "debugver": 4,
        }
    def elaborate(self, _):
        return self.latch_partial_value_with_no_side_effect(fields=["step", "ebreakm"])


class MSCRATCH(CSR_Write_Handler):
    addr = CSRIndex.MSCRATCH
    
    def elaborate(self, _):
        return self.latch_whole_value_with_no_side_effect()


class MHARTID(CSR_Write_Handler):
    addr = CSRIndex.MHARTID

    def elaborate(self, _):
        return self.latch_whole_value_with_no_side_effect()


class MCAUSE(CSR_Write_Handler):
    addr = CSRIndex.MCAUSE
    layout = MCAUSE_Layout

    def elaborate(self, _):
        return self.latch_whole_value_with_no_side_effect()


class MSTATUS(CSR_Write_Handler):
    addr = CSRIndex.MSTATUS
    layout = MSTATUS_Layout

     # TODO dangerous (doesn't implement WARL) - change it
    def elaborate(self, _):
        return self.latch_whole_value_with_no_side_effect()

class MIE(CSR_Write_Handler):
    addr = CSRIndex.MIE
    layout = MIE_Layout

    def elaborate(self, _):
        return self.latch_whole_value_with_no_side_effect()

class MIP(CSR_Write_Handler):
    addr = CSRIndex.MIP
    layout = MIP_Layout

    # TODO
    # For now it's fully readonly - doesn't support software interrupts,
    # normally triggered via write to {m|s|u}sip field.
    def elaborate(self, _):
        return Module()

class SATP(CSR_Write_Handler):
    addr = CSRIndex.SATP
    layout = SATP_Layout

    def elaborate(self, _):
        return self.latch_partial_value_with_no_side_effect(fields=["ppn", "mode"])


class MTIME(CSR_Write_Handler):
    addr = CSRNonStandardIndex.MTIME

    def elaborate(self, _):
        return self.latch_whole_value_with_no_side_effect()

class MTIMECMP(CSR_Write_Handler):
    addr = CSRNonStandardIndex.MTIMECMP

    # TODO - for now i commented out some timer IRQ functionality
    # # From https://forums.sifive.com/t/how-to-clear-interrupt-in-interrupt-handler/2781:
    # # The timer interrupt for example is cleared with writing a new value to the mtimecmp register (which must be higher than the current timer value).
    # m.d.sync += [
    #     self.csr_unit.mip.mtip.eq(0)
    # ]

    def elaborate(self, _):
        return self.latch_whole_value_with_no_side_effect()
