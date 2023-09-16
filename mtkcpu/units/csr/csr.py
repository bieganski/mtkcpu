from typing import Sequence

from amaranth import Signal, Elaboratable, Module

from mtkcpu.utils.common import matcher
from mtkcpu.cpu.isa import Funct3, InstrType
from mtkcpu.cpu.priv_isa import *
from mtkcpu.units.csr.csr_handlers import *


def _is(x, ys):
    from functools import reduce
    from operator import or_
    return reduce(or_, [x == y for y in ys])


class CsrUnit(Elaboratable):
    @staticmethod
    def enabled_csr_regs(with_virtual_memory: bool) -> Sequence[type]:
        regs = {
            MISA,
            MTVEC,
            MTVAL,
            MEPC,
            DPC,
            MSCRATCH,
            MHARTID,
            MCAUSE,
            MTIME,
            MTIMECMP,
            MSTATUS,
            MIE,
            MIP,
            DCSR,
        }
        if with_virtual_memory:
            regs.add(SATP)
        return regs

    def reg_by_addr(self, addr : CSRNonStandardIndex | CSRIndex) -> CSR_Write_Handler:
        matches = [x for x in self.csr_regs if x.addr == addr]
        if len(matches) != 1:
            raise ValueError(f"Expected to find a single CSR with address {hex(addr)}, got {matches} instead!")
        return matches[0]

    # simplify direct access, e.g. csr_unit.mtvec
    def __getattr__(self, name: str) -> data.View:
        def get_name(handler: CSR_Write_Handler) -> str:
            return handler.__class__.__name__
        matches = [x for x in self.csr_regs if get_name(x).lower() == name.lower()]
        if len(matches) != 1:
            raise ValueError(f"Expected to find a single CSR named {name}, got {matches} instead!")
        match = matches[0]
        return data.View(match.layout, match.my_reg_latch)

    def __init__(self,
                 in_machine_mode : Signal,
                 in_debug_mode : Signal,
                 with_virtual_memory: bool,
                ):
        # Input signals.
        self.csr_idx = Signal(CSRIndex)
        assert self.csr_idx.width == 12
        self.rs1 = Signal(5) # either rs1 or umm[4:0]
        self.rd = Signal(5)
        self.rs1val = Signal(32)
        self.func3 = Signal(Funct3)
        self.en = Signal()
        self.in_machine_mode = in_machine_mode
        self.in_debug_mode = in_debug_mode
        self.with_virtual_memory = with_virtual_memory

        # Output signals.
        self.rd_val = Signal(32)
        self.vld = Signal()
        self.illegal_insn = Signal()

        self.csr_regs = [x(my_reg_latch=Signal(32)) for x in __class__.enabled_csr_regs(with_virtual_memory=with_virtual_memory)]
    
    def elaborate(self, platform):
        m = self.m = Module()
        m.submodules += self.csr_regs
        sync = m.d.sync
        comb = m.d.comb

        rd_latch = Signal.like(self.rd)
        rs1_latch = Signal.like(self.rs1)
        func3_latch = Signal.like(self.func3)
        csr_idx_latch = Signal.like(self.csr_idx)
        
        with m.FSM():
            with m.State("IDLE"):
                with m.If(self.en):
                    with m.If(~self.in_machine_mode):
                        m.d.comb += self.illegal_insn.eq(1)
                    with m.Else():
                        with m.Switch(self.csr_idx):
                            for reg in self.csr_regs:
                                with m.Case(reg.addr):
                                    sync += [
                                        rd_latch.eq(self.rd),
                                        rs1_latch.eq(self.rs1),
                                        func3_latch.eq(self.func3),
                                        csr_idx_latch.eq(self.csr_idx),
                                    ]
                                    m.next = "REG_GENERIC"

                                    # Debug Specs 1.0, 4.10:
                                    # 'These registers are only accessible from Debug Mode.'
                                    if reg.addr in range(0x7b0, 0x7b4):
                                        with m.If(~self.in_debug_mode):
                                            # TODO: slippery code here - needs to be reverified.
                                            m.d.comb += self.illegal_insn.eq(1)
                                            m.next = "IDLE"
                            with m.Default():
                                m.d.comb += self.illegal_insn.eq(1)
            with m.State("REG_GENERIC"):
                # all CSRxx insructions do read.
                # NOTE from doc:
                # If rd=x0, then the instruction shall not read the CSR and shall not 
                # cause any of the side effects that might occur on a CSR read.
                # however, we don't support read side-effects, so we skip that check (and save on resources).
                with m.Switch(csr_idx_latch):
                    for reg in self.csr_regs:
                        with m.Case(reg.addr):
                            m.d.sync += self.rd_val.eq(reg.my_reg_latch)

                dst = Signal(32)
                
                with m.Switch(csr_idx_latch):
                    for reg in self.csr_regs:
                        with m.Case(reg.addr):
                            src = reg.my_reg_latch
                            with m.If(_is(func3_latch, [Funct3.CSRRS, Funct3.CSRRSI])):
                                m.d.sync += dst.eq(src | self.rs1val)
                            with m.Elif(_is(func3_latch, [Funct3.CSRRC, Funct3.CSRRCI])):
                                m.d.sync += dst.eq(src & ~self.rs1val)
                            with m.Elif(_is(func3_latch, [Funct3.CSRRW, Funct3.CSRRWI])):
                                m.d.sync += dst.eq(self.rs1val)
                m.next = "REG_SPECIFIC"
            with m.State("REG_SPECIFIC"):
                with m.Switch(csr_idx_latch):
                    for reg in self.csr_regs:
                        with m.Case(reg.addr):
                            # NOTE from doc:
                            # For both CSRRS and CSRRC, if rs1=x0, then the instruction will not write 
                            # to the CSR at all, and so shall not cause any of the side effects 
                            # that might otherwise occur on a CSR write,
                            with m.If(_is(func3_latch, [Funct3.CSRRS, Funct3.CSRRC]) & (rs1_latch == 0)):
                                m.next = "FINISH"
                            with m.Else():
                                comb += [
                                    reg.active.eq(1),
                                    reg.write_value.eq(dst)
                                ]
                                with m.If(reg.write_finished):
                                    m.next = "FINISH"
            with m.State("FINISH"):
                m.next = "IDLE"
                comb += [
                    self.vld.eq(1)
                ]

        return m

match_csr = matcher(
    [
        (InstrType.SYSTEM, Funct3.CSRRW),
        (InstrType.SYSTEM, Funct3.CSRRS),
        (InstrType.SYSTEM, Funct3.CSRRC),

        (InstrType.SYSTEM, Funct3.CSRRWI),
        (InstrType.SYSTEM, Funct3.CSRRSI),
        (InstrType.SYSTEM, Funct3.CSRRCI),
    ]
)
