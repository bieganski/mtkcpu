from typing import Callable, Dict, List, Union

from amaranth import Signal, Elaboratable, Module
from grpc import Call

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
        regs : List[RegisterCSR] = {
            MISA(),
            MTVEC(),
            MTVAL(),
            MEPC(),
            MSCRATCH(),
            MHARTID(),
            MCAUSE(),
            MTIME(),
            MTIMECMP(),
            MSTATUS(),
            MIE(),
            MIP(),
        }
        
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


    def __init__(self, in_machine_mode : Signal):
        # Input signals.
        self.csr_idx = Signal(CSRIndex)
        assert self.csr_idx.width == 12
        self.rs1 = Signal(5) # either rs1 or umm[4:0]
        self.rd = Signal(5)
        self.rs1val = Signal(32)
        self.func3 = Signal(Funct3)
        self.en = Signal()
        self.in_machine_mode = in_machine_mode

        # Debug
        self.ONREAD = Signal()
        self.ONWRITE = Signal()
        
        # Output signals.
        self.rd_val = Signal(32)
        self.vld = Signal()
        self.illegal_insn = Signal()

        self.controller = ControllerInterface()
        self.csr_regs = self.enabled_csr_regs(self.controller)
    
    def on_read(self):
        m : Module = self.m
        m.d.comb += self.ONREAD.eq(1)
        with m.Switch(self.csr_idx):
            for reg in self.csr_regs:
                register = reg.rec.w if isinstance(reg, WriteOnlyRegisterCSR) else reg.rec.r
                with m.Case(reg.csr_idx):
                    m.d.sync += self.rd_val.eq(register)

    def on_write(self):
        m : Module = self.m
        m.d.comb += self.ONWRITE.eq(1)
        with m.Switch(self.csr_idx):
            for reg in self.csr_regs:
                with m.Case(reg.csr_idx):
                    if isinstance(reg, ReadOnlyRegisterCSR):
                        continue
                    m.d.sync += reg.rec.w.eq(self.rs1val)  # VERY NOT TRUE FOR CSRR{S|C} with rs1 != x0

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
                        sync += [
                            rd_latch.eq(self.rd),
                            rs1_latch.eq(self.rs1),
                            func3_latch.eq(self.func3),
                            csr_idx_latch.eq(self.csr_idx),
                        ]
                        m.next = "RW_GENERIC"
            with m.State("RW_GENERIC"):
                # read and write conditions are described in CSR docs.
                with m.If(~(_is(func3_latch, [Funct3.CSRRW, Funct3.CSRRWI]) & (rd_latch == 0))):
                    self.on_read()
                with m.If(~(_is(func3_latch, [Funct3.CSRRS, Funct3.CSRRSI, Funct3.CSRRC, Funct3.CSRRCI]) & (rs1_latch == 0))):
                    self.on_write()
                    m.next = "WRITE"
                with m.Else():
                    m.next = "FINISH"
            with m.State("WRITE"):
                with m.Switch(csr_idx_latch):
                    for reg in self.csr_regs:
                        with m.Case(reg.csr_idx):
                            reg.handle_write()
                with m.If(self.controller.handler_done):
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
