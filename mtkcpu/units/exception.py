# Following file comes (with small changes) from minerva, A 32-bit RISC-V soft processor
# https://github.com/minerva-cpu/minerva

from amaranth import *
from amaranth.lib.coding import PriorityEncoder

from mtkcpu.cpu.priv_isa import *
from mtkcpu.units.csr.csr import CsrUnit

class ExceptionUnit(Elaboratable):
    def __init__(self, current_priv_mode: Signal, csr_unit : CsrUnit):
        self.mtvec = csr_unit.mtvec
        self.mtval = csr_unit.mtval
        self.mepc = csr_unit.mepc
        self.mcause = csr_unit.mcause
        self.mie = csr_unit.mie
        self.mstatus = csr_unit.mstatus
        self.mip = csr_unit.mip

        self.external_interrupt = Signal() # not supported for now
        self.timer_interrupt = Signal()
        self.software_interrupt = Signal() # not supported for now

        # TODO move those to 'elaborate' function
        self.m_illegal = Signal()
        self.m_ebreak = Signal()
        self.m_ecall = Signal()
        
        # those are set by memory system.
        self.m_fetch_misaligned = Signal()
        self.m_load_misaligned = Signal()
        self.m_store_misaligned = Signal()
        self.m_fetch_error = Signal()
        self.m_load_error = Signal()
        self.m_store_error = Signal()
        self.badaddr = Signal(32)
        
        # self.m_branch_target = Signal(32)

        self.m_pc = Signal(32)
        self.m_instruction = Signal(32)
        
        self.m_mret = Signal()
        self.m_raise = Signal()

        self.current_priv_mode = current_priv_mode

        self.trap_cause_map = {
            TrapCause.FETCH_MISALIGNED : self.m_fetch_misaligned,
            TrapCause.FETCH_ACCESS_FAULT : self.m_fetch_error,
            TrapCause.ILLEGAL_INSTRUCTION : self.m_illegal,
            TrapCause.BREAKPOINT : self.m_ebreak,
            TrapCause.LOAD_MISALIGNED : self.m_load_misaligned,
            TrapCause.LOAD_ACCESS_FAULT : self.m_load_error,
            TrapCause.STORE_MISALIGNED : self.m_store_misaligned,
            TrapCause.STORE_ACCESS_FAULT : self.m_store_error,
            TrapCause.ECALL_FROM_M : self.m_ecall,
        }

        self.irq_cause_map = {
            IrqCause.U_SOFTWARE_INTERRUPT : self.software_interrupt,
            IrqCause.S_SOFTWARE_INTERRUPT : self.software_interrupt,
            IrqCause.M_SOFTWARE_INTERRUPT : self.software_interrupt,
            IrqCause.U_TIMER_INTERRUPT : self.timer_interrupt,
            IrqCause.S_TIMER_INTERRUPT : self.timer_interrupt,
            IrqCause.M_TIMER_INTERRUPT : self.timer_interrupt,
            IrqCause.U_EXTERNAL_INTERRUPT : self.external_interrupt,
            IrqCause.S_EXTERNAL_INTERRUPT : self.external_interrupt,
            IrqCause.M_EXTERNAL_INTERRUPT : self.external_interrupt,
        }

    def elaborate(self, platform):
        m = Module()

        from mtkcpu.units.csr.types import MIE_Layout, MIP_Layout, MSTATUS_Layout, MCAUSE_Layout
        mie : MIE_Layout = self.mie.as_view()
        mip : MIP_Layout = self.mip.as_view()
        mstatus : MSTATUS_Layout = self.mstatus.as_view()
        mcause : MCAUSE_Layout = self.mcause.as_view()
        mepc = self.mepc.as_view()
        mtval = self.mtval.as_view()


        trap_pe = m.submodules.trap_pe = PriorityEncoder(16)
        for k, v in self.trap_cause_map.items():
            m.d.comb += trap_pe.i[k].eq(v)
        
        interrupt_pe = m.submodules.interrupt_pe = PriorityEncoder(16)
        m.d.comb += [
            interrupt_pe.i[IrqCause.M_SOFTWARE_INTERRUPT].eq(mie.msie), # self.mip.r.msip & self.mie.r.msie),
            interrupt_pe.i[IrqCause.M_TIMER_INTERRUPT   ].eq(mie.mtie & self.timer_interrupt), # self.mip.r.mtip & self.mie.r.mtie),
            interrupt_pe.i[IrqCause.M_EXTERNAL_INTERRUPT].eq(mie.meie), # self.mip.r.meip & self.mie.r.meie)
        ]

        m.d.comb += self.m_raise.eq(~trap_pe.n | (~interrupt_pe.n & mstatus.mie))
        with m.If(self.m_raise):
            m.d.sync += [
                mstatus.mpp.eq(self.current_priv_mode),
                self.current_priv_mode.eq(PrivModeBits.MACHINE), # will be changed when impl. either supervisor or mdeleg register.
            ]
            m.d.sync += [
                mip.msip.eq(self.software_interrupt),
                mip.mtip.eq(self.timer_interrupt),
                mip.meip.eq(self.external_interrupt)
            ]
            m.d.sync += [
                mstatus.mpie.eq(mstatus.mie),
                mstatus.mie.eq(0),
                mepc.eq(self.m_pc)
            ]
            with m.If(~trap_pe.n):
                m.d.sync += [
                    mcause.ecode.eq(trap_pe.o),
                    mcause.interrupt.eq(0)
                ]
                with m.Switch(trap_pe.o):
                    # with m.Case(Cause.FETCH_MISALIGNED):
                    #     m.d.sync += self.mtval.eq(self.m_branch_target)
                    with m.Case(TrapCause.FETCH_ACCESS_FAULT):
                        m.d.sync += mtval.eq(self.badaddr)
                    with m.Case(TrapCause.ILLEGAL_INSTRUCTION):
                        m.d.sync += mtval.eq(self.m_instruction)
                    # with m.Case(Cause.BREAKPOINT):
                    #     m.d.sync += self.mtval.eq(self.m_pc)
                    # with m.Case(Cause.LOAD_MISALIGNED, Cause.STORE_MISALIGNED):
                    #     m.d.sync += self.mtval.eq(self.m_result)
                    with m.Case(TrapCause.LOAD_ACCESS_FAULT, TrapCause.STORE_ACCESS_FAULT):
                        m.d.sync += mtval.eq(self.badaddr)
                    # with m.Case():
                    #     m.d.sync += self.mtval.r.eq(0) # XXX
            with m.Else():
                m.d.sync += [
                    mcause.ecode.eq(interrupt_pe.o),
                    mcause.interrupt.eq(1)
                ]
        with m.Elif(self.m_mret):
            m.d.sync += [
                self.mstatus.as_view().mie.eq(self.mstatus.as_view().mpie),
                self.current_priv_mode.eq(self.mstatus.as_view().mpp) # pop privilege mode
            ]

        return m
