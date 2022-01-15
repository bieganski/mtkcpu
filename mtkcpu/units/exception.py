# Following file comes (with small changes) from minerva, A 32-bit RISC-V soft processor
# https://github.com/minerva-cpu/minerva

from amaranth import *
from amaranth.lib.coding import PriorityEncoder

from mtkcpu.cpu.csr import *
from mtkcpu.cpu.priv_isa import *


__all__ = ["ExceptionUnit"]

from mtkcpu.units.csr import CsrUnit

class ExceptionUnit(Elaboratable):
    def __init__(self, csr_unit : CsrUnit):

        self.mtvec = csr_unit.mtvec
        self.mtval = csr_unit.mtval
        self.mepc = csr_unit.mepc
        self.mcause = csr_unit.mcause

        self.external_interrupt = Signal(32)
        self.timer_interrupt = Signal()
        self.software_interrupt = Signal()

        self.m_fetch_misaligned = Signal()
        self.m_fetch_error = Signal()
        self.m_fetch_badaddr = Signal(30)
        self.m_load_misaligned = Signal()
        self.m_load_error = Signal()
        self.m_store_misaligned = Signal()
        self.m_store_error = Signal()
        self.m_loadstore_badaddr = Signal(30)
        self.m_branch_target = Signal(32)
        self.m_illegal = Signal()
        self.m_ebreak = Signal()
        self.m_ecall = Signal()
        self.m_pc = Signal(32)
        self.m_instruction = Signal(32)
        self.m_result = Signal(32)
        self.m_mret = Signal()

        self.m_raise = Signal()

        self.trap_cause_map = {
            Cause.FETCH_MISALIGNED : self.m_fetch_misaligned,
            Cause.FETCH_ACCESS_FAULT : self.m_fetch_error,
            Cause.ILLEGAL_INSTRUCTION : self.m_illegal,
            Cause.BREAKPOINT : self.m_ebreak,
            Cause.LOAD_MISALIGNED : self.m_load_misaligned,
            Cause.LOAD_ACCESS_FAULT : self.m_load_error,
            Cause.STORE_MISALIGNED : self.m_store_misaligned,
            Cause.STORE_ACCESS_FAULT : self.m_store_error,
            Cause.ECALL_FROM_M : self.m_ecall,
        }

    def elaborate(self, platform):
        m = Module()

        trap_pe = m.submodules.trap_pe = PriorityEncoder(16)
        for k, v in self.trap_cause_map.items():
            m.d.comb += trap_pe.i[k].eq(v)

        # m.d.sync += [
        #     self.irq_pending.r.eq(self.external_interrupt & self.irq_mask.r),
        #     self.mip.r.msip.eq(self.software_interrupt),
        #     self.mip.r.mtip.eq(self.timer_interrupt),
        #     self.mip.r.meip.eq(self.irq_pending.r.bool())
        # ]
        
        # interrupt_pe = m.submodules.interrupt_pe = PriorityEncoder(16)
        # m.d.comb += [
        #     interrupt_pe.i[Cause.M_SOFTWARE_INTERRUPT].eq(self.mip.r.msip & self.mie.r.msie),
        #     interrupt_pe.i[Cause.M_TIMER_INTERRUPT   ].eq(self.mip.r.mtip & self.mie.r.mtie),
        #     interrupt_pe.i[Cause.M_EXTERNAL_INTERRUPT].eq(self.mip.r.meip & self.mie.r.meie)
        # ]

        m.d.comb += self.m_raise.eq(~trap_pe.n) # XXX | ~interrupt_pe.n & self.mstatus.r.mie)

        with m.If(self.m_raise):
            m.d.sync += [
                # self.mstatus.r.mpie.eq(self.mstatus.r.mie),
                # self.mstatus.r.mie.eq(0),
                self.mepc.eq(self.m_pc + 4)
            ]
            with m.If(~trap_pe.n):
                m.d.sync += [
                    self.mcause.ecode.eq(trap_pe.o),
                    self.mcause.interrupt.eq(0)
                ]
                with m.Switch(trap_pe.o):
                    # with m.Case(Cause.FETCH_MISALIGNED):
                    #     m.d.sync += self.mtval.eq(self.m_branch_target)
                    # with m.Case(Cause.FETCH_ACCESS_FAULT):
                    #     m.d.sync += self.mtval.eq(self.m_fetch_badaddr << 2)
                    with m.Case(Cause.ILLEGAL_INSTRUCTION):
                        m.d.sync += self.mtval.eq(self.m_instruction)
                    # with m.Case(Cause.BREAKPOINT):
                    #     m.d.sync += self.mtval.eq(self.m_pc)
                    # with m.Case(Cause.LOAD_MISALIGNED, Cause.STORE_MISALIGNED):
                    #     m.d.sync += self.mtval.eq(self.m_result)
                    # with m.Case(Cause.LOAD_ACCESS_FAULT, Cause.STORE_ACCESS_FAULT):
                    #     m.d.sync += self.mtval.eq(self.m_loadstore_badaddr << 2)
                    # with m.Case():
                    #     m.d.sync += self.mtval.r.eq(0) # XXX
            # with m.Else():
            #     m.d.sync += [
            #         self.mcause.r.ecode.eq(interrupt_pe.o),
            #         self.mcause.r.interrupt.eq(1)
            #     ]
        # with m.Elif(self.m_mret):
        #     m.d.sync += self.mstatus.r.mie.eq(self.mstatus.r.mpie)

        return m
