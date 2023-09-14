from typing import Callable, Dict, List, Union

from amaranth import Signal, Elaboratable, Module

from mtkcpu.utils.common import matcher
from mtkcpu.cpu.isa import Funct3, InstrType
from mtkcpu.cpu.priv_isa import *
from mtkcpu.units.csr_handlers import *


def _is(x, ys):
    from functools import reduce
    from operator import or_
    return reduce(or_, [x == y for y in ys])

# RegisterCSR handlers do communicate with CsrUnit via signals defined here.
class ControllerInterface():
    def __init__(self):
        self.handler_done = Signal()


class CsrUnit(Elaboratable):
    def enabled_csr_regs(self, controller : ControllerInterface):
        regs : set[RegisterCSR] = {
            MISA(),
            MTVEC(),
            MTVAL(),
            MEPC(),
            DPC(),
            MSCRATCH(),
            MHARTID(),
            MCAUSE(),
            MTIME(),
            MTIMECMP(),
            MSTATUS(),
            MIE(),
            MIP(),
            DCSR(),
        }

        if self.with_virtual_memory:
            regs.add(SATP())
        
        def sanity_check():
            for r in regs:
                r.associate_with_csr_unit(controller, self)
            for r in regs:
                assert len(r.rec.r) == 32
        sanity_check()
        return regs

    def reg_by_addr(self, addr : Union[CSRIndex, CSRNonStandardIndex]) -> RegisterCSR:
        all = [x for x in self.csr_regs if x.csr_idx == addr]
        if not all:
            raise ValueError(f"CSR with address {hex(addr)} not defined!")
        return all[0]

    # simplify direct access, e.g. csr_unit.mtvec
    def __getattr__(self, name):
        for reg in self.csr_regs:
            if reg.name == name:
                if isinstance(reg, WriteOnlyRegisterCSR):
                    return reg.rec.w
                elif isinstance(reg, ReadOnlyRegisterCSR):
                    return reg.rec.r
                elif isinstance(reg, RegisterCSR):
                    return reg.rec.r
                else:
                    assert False
        raise ValueError(f"CSRUnit: Not found register named {name}")


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

        # Debug
        self.ONREAD = Signal()
        self.ONWRITE = Signal()
        self.ONSET = Signal()
        self.ONCLEAR = Signal()
        
        # Output signals.
        self.rd_val = Signal(32)
        self.vld = Signal()
        self.illegal_insn = Signal()

        self.controller = ControllerInterface()
        self.csr_regs = self.enabled_csr_regs(self.controller)
    
    def elaborate(self, platform):
        m = self.m = Module()
        sync = m.d.sync
        comb = m.d.comb

        rd_latch = Signal.like(self.rd)
        rs1_latch = Signal.like(self.rs1)
        func3_latch = Signal.like(self.func3)
        csr_idx_latch = Signal.like(self.csr_idx)
        
        with m.FSM() as fsm:
            with m.State("IDLE"):
                with m.If(self.en):
                    with m.If(~self.in_machine_mode):
                        m.d.comb += self.illegal_insn.eq(1)
                    with m.Else():
                        with m.Switch(self.csr_idx):
                            for reg in self.csr_regs:
                                with m.Case(reg.csr_idx):
                                    sync += [
                                        rd_latch.eq(self.rd),
                                        rs1_latch.eq(self.rs1),
                                        func3_latch.eq(self.func3),
                                        csr_idx_latch.eq(self.csr_idx),
                                    ]
                                    m.next = "REG_GENERIC"

                                    # Debug Specs 1.0, 4.10:
                                    # 'These registers are only accessible from Debug Mode.'
                                    if reg.csr_idx in range(0x7b0, 0x7b4):
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
                # however, we don't support read side-effects, so we can save one mux here.
                with m.Switch(csr_idx_latch):
                    for reg in self.csr_regs:
                        with m.Case(reg.csr_idx):
                            register = reg.rec.w if isinstance(reg, WriteOnlyRegisterCSR) else reg.rec.r
                            m.d.sync += self.rd_val.eq(register)

                with m.Switch(csr_idx_latch):
                    for reg in self.csr_regs:
                        with m.Case(reg.csr_idx):
                            if isinstance(reg, ReadOnlyRegisterCSR):
                                continue
                            src = reg.rec.w if isinstance(reg, WriteOnlyRegisterCSR) else reg.rec.r
                            dst = reg.rec.w # always exists
                            # TODO it needs to use rec.r
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
                        with m.Case(reg.csr_idx):
                            # NOTE from doc:
                            # For both CSRRS and CSRRC, if rs1=x0, then the instruction will not write 
                            # to the CSR at all, and so shall not cause any of the side effects 
                            # that might otherwise occur on a CSR write,
                            need_wait = Signal()
                            with m.If(need_wait):
                                with m.If(self.controller.handler_done):
                                    m.next = "FINISH"
                            with m.Else():
                                # covers all non-waiting paths.
                                m.next = "FINISH"
                            
                            with m.If(_is(func3_latch, [Funct3.CSRRS, Funct3.CSRRC])):
                                with m.If(rs1_latch != 0):
                                    reg.handle_write()
                                    comb += need_wait.eq(1)
                            with m.Else():
                                reg.handle_write()
                                comb += need_wait.eq(1)
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
