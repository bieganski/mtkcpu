#!/usr/bin/env python3
from __future__ import with_statement
from functools import reduce
from operator import or_

from typing import Union, Optional
from amaranth import Mux, Cat, Signal, Const, Record, Elaboratable, Module, Memory, signed
from amaranth.hdl.rec import Layout
from amaranth import unsigned
from amaranth.lib import data

from mtkcpu.units.csr import CsrUnit, match_csr
from mtkcpu.units.exception import ExceptionUnit
from mtkcpu.utils.common import CODE_START_ADDR, EBRMemConfig
from mtkcpu.units.adder import AdderUnit, match_adder_unit
from mtkcpu.units.compare import CompareUnit, match_compare_unit
from mtkcpu.units.loadstore import (MemoryArbiter, MemoryUnit,
                                    match_load, match_loadstore_unit)
from mtkcpu.units.logic import LogicUnit, match_logic_unit
from mtkcpu.units.shifter import ShifterUnit, match_shifter_unit
from mtkcpu.units.upper import match_auipc, match_lui
from mtkcpu.utils.common import matcher
from mtkcpu.cpu.isa import Funct3, InstrType, Funct7
from mtkcpu.units.debug.top import DebugUnit
from mtkcpu.cpu.priv_isa import IrqCause, TrapCause, PrivModeBits
from mtkcpu.units.debug.cpu_dm_if import CpuRunningState, CpuRunningStateExternalInterface

match_jal = matcher(
    [
        (InstrType.JAL,),
    ]
)

match_jalr = matcher(
    [
        (InstrType.JALR, Funct3.JALR),
    ]
)

match_branch = matcher(
    [
        (InstrType.BRANCH, Funct3.BEQ),
        (InstrType.BRANCH, Funct3.BNE),
        (InstrType.BRANCH, Funct3.BLT),
        (InstrType.BRANCH, Funct3.BGE),
        (InstrType.BRANCH, Funct3.BLTU),
        (InstrType.BRANCH, Funct3.BGEU),
    ]
)

match_mret = matcher(
    [
        (InstrType.SYSTEM, Funct3.PRIV, Funct7.MRET),
    ]
)

match_sfence_vma = matcher(
    [
        (InstrType.SYSTEM, Funct3.PRIV, Funct7.SFENCE_VMA),
    ]
)


class ActiveUnitLayout(Layout):
    def __init__(self):
        super().__init__(
            [
                ("logic", 1),
                ("adder", 1),
                ("shifter", 1),
                ("mem_unit", 1),
                ("compare", 1),
                ("lui", 1),
                ("auipc", 1),
                ("jal", 1),
                ("jalr", 1),
                ("branch", 1),
                ("csr", 1),
                ("mret", 1)
            ]
        )


class ActiveUnit(Record):
    def __init__(self):
        super().__init__(ActiveUnitLayout(), name="active_unit")


class MtkCpu(Elaboratable):
    def __init__(self, mem_config: EBRMemConfig, reg_init=[0 for _ in range(32)], with_debug=True):

        if len(reg_init) > 32:
            raise ValueError(
                f"Register init length (={len(reg_init)}) exceedes 32!"
            )

        if reg_init[0] != 0:
            print(
                f"WARNING, register x0 set to value {reg_init[0]}, however it will be overriden with zero (due to RiscV spec).."
            )
            reg_init[0] = 0

        self.mem_config = mem_config
        self.with_debug = with_debug

        # 0xDE for debugging (uninitialized data magic byte)
        self.reg_init = reg_init + [0x0] * (len(reg_init) - 32)

        # input signals
        self.mem_in_vld = Signal()
        self.mem_out_rdy = Signal()
        self.mem_in_data = Signal(32)

        # output signals
        self.mem_in_rdy = Signal()
        self.mem_out_vld = Signal()
        self.mem_out_data = Signal(32)

        self.gprf_debug_addr = Signal(32)
        self.gprf_debug_data = Signal(32)
        self.gprf_debug_write_en = Signal()

        if self.with_debug:
            self.debug = DebugUnit(self)

        self.regs = Memory(width=32, depth=32, init=self.reg_init)

        self.running_state = CpuRunningState()
        self.running_state_interface = CpuRunningStateExternalInterface()


    def elaborate(self, platform):
        self.m = m = Module()

        comb = m.d.comb
        sync = m.d.sync

        # CPU units used.
        logic = m.submodules.logic = LogicUnit()
        adder = m.submodules.adder = AdderUnit()
        shifter = m.submodules.shifter = ShifterUnit()
        compare = m.submodules.compare = CompareUnit()
        
        self.current_priv_mode = Signal(PrivModeBits, reset=PrivModeBits.MACHINE)
        
        csr_unit = self.csr_unit = m.submodules.csr_unit = CsrUnit(
            # TODO does '==' below produces the same synth result as .all()?
            in_machine_mode=self.current_priv_mode==PrivModeBits.MACHINE
        )
        exception_unit = self.exception_unit = m.submodules.exception_unit = ExceptionUnit(
            csr_unit=csr_unit, 
            current_priv_mode=self.current_priv_mode
        )
        arbiter = self.arbiter = m.submodules.arbiter = MemoryArbiter(
            mem_config=self.mem_config, 
            with_addr_translation=True, 
            csr_unit=csr_unit, # SATP register
            exception_unit=exception_unit, # current privilege mode
        )

        if self.with_debug:
            m.submodules.debug = self.debug
            m.submodules.dm_cpu_if = self.running_state_interface
            self.debug_bus = arbiter.port(priority=0)

        self.dbus = arbiter.port(priority=1)
        mem_unit = m.submodules.mem_unit = MemoryUnit(
            mem_port=self.dbus
        )

        ibus = self.ibus = arbiter.port(priority=2)

        # Current decoding state signals.
        instr = self.instr = Signal(32)
        funct3 = self.funct3 = Signal(3)
        funct7 = self.funct7 = Signal(7)
        rd = self.rd = Signal(5)
        rs1 = Signal(5)
        rs2 = Signal(5)
        rs1val = Signal(32)
        rs2val = Signal(32)
        rdval = Signal(32)  # calculated by unit, stored to register file
        imm = Signal(signed(12))
        csr_idx = Signal(12)
        uimm = Signal(20)
        opcode = self.opcode = Signal(InstrType)
        pc = self.pc = Signal(32, reset=CODE_START_ADDR)

        # at most one active_unit at any time
        active_unit = ActiveUnit()

        # Register file. Contains two read ports (for rs1, rs2) and one write port.
        regs = self.regs
        reg_read_port1 = self.reg_read_port1 = m.submodules.reg_read_port1 = regs.read_port()
        reg_read_port2 = m.submodules.reg_read_port2 = regs.read_port()
        reg_write_port = (
            self.reg_write_port
        ) = m.submodules.reg_write_port = regs.write_port()

        # Timer management.
        mtime = self.mtime = Signal(32)
        sync += mtime.eq(mtime + 1)
        comb += csr_unit.mtime.eq(mtime)

        # with m.If(csr_unit.mstatus.mie & csr_unit.mie.mtie):
        #     with m.If(mtime == csr_unit.mtimecmp):
        #         # 'halt' signal needs to be cleared when CPU jumps to trap handler.
        #         sync += [
        #             self.halt.eq(1),
        #         ]

        def prev(sig: Signal) -> Signal:
            res = Signal()
            m.d.sync += res.eq(sig)
            return res

        just_resumed = self.just_resumed = Signal()
        just_halted  = self.just_halted  = Signal()

        comb += [
            just_resumed.eq(prev(self.running_state.halted) & ~self.running_state.halted),
            just_halted.eq(~prev(self.running_state.halted) &  self.running_state.halted),
        ]

        with m.If(self.running_state.halted & self.running_state_interface.resumereq):
            # from specs:
            # 
            # When a debugger writes 1 to resumereq, each selected hart’s resume ack bit 
            # is cleared and each selected, halted hart is sent a resume request. 
            sync += [
                self.running_state.halted.eq(0),
            ]
        with m.If(just_resumed):
            comb += self.running_state_interface.resumeack.eq(1)
        with m.If(just_halted):
            comb += self.running_state_interface.haltack.eq(1)

        comb += [
            exception_unit.m_instruction.eq(instr),
            exception_unit.m_pc.eq(pc),
        ]

        # DebugModule is able to read and write GPR values.
        with m.If(self.running_state.halted):
            comb += [
                reg_read_port1.addr.eq(self.gprf_debug_addr),
                reg_write_port.addr.eq(self.gprf_debug_addr),
                reg_write_port.en.eq(self.gprf_debug_write_en)
            ]

            # Swap data register assignment direction, depending on 'write_en'
            with m.If(self.gprf_debug_write_en):
                comb += reg_write_port.data.eq(self.gprf_debug_data)
            with m.Else():
                comb += self.gprf_debug_data.eq(reg_read_port1.data)
        
        with m.Else():
            comb += [
                reg_read_port1.addr.eq(rs1),
                reg_read_port2.addr.eq(rs2),
                
                reg_write_port.addr.eq(rd),
                reg_write_port.data.eq(rdval),

                rs1val.eq(reg_read_port1.data),
                rs2val.eq(reg_read_port2.data),
            ]

        comb += [
            # following is not true for all instrutions, but in specific cases will be overwritten later
            imm.eq(instr[20:32]),
            csr_idx.eq(instr[20:32]),
            uimm.eq(instr[12:]),
        ]

        # drive input signals of actually used unit.
        with m.If(active_unit.logic):
            comb += [
                logic.funct3.eq(funct3),
                logic.src1.eq(rs1val),
                logic.src2.eq(Mux(opcode == InstrType.OP_IMM, imm, rs2val)),
            ]
        with m.Elif(active_unit.adder):
            comb += [
                adder.src1.eq(rs1val),
                adder.src2.eq(Mux(opcode == InstrType.OP_IMM, imm, rs2val)),
            ]
        with m.Elif(active_unit.shifter):
            comb += [
                shifter.funct3.eq(funct3),
                shifter.funct7.eq(funct7),
                shifter.src1.eq(rs1val),
                shifter.shift.eq(
                    Mux(
                        opcode == InstrType.OP_IMM, imm[0:5].as_unsigned(), rs2val[0:5]
                    )
                ),
            ]
        with m.Elif(active_unit.mem_unit):
            comb += [
                mem_unit.en.eq(1),
                mem_unit.funct3.eq(funct3),
                mem_unit.src1.eq(rs1val),
                mem_unit.src2.eq(rs2val),
                mem_unit.store.eq(opcode == InstrType.STORE),
                mem_unit.offset.eq(
                    Mux(opcode == InstrType.LOAD, imm, Cat(rd, imm[5:12]))
                ),
            ]
        with m.Elif(active_unit.compare):
            comb += [
                compare.funct3.eq(funct3),
                # Compare Unit uses Adder for carry and overflow flags.
                adder.src1.eq(rs1val),
                adder.src2.eq(Mux(opcode == InstrType.OP_IMM, imm, rs2val)),
                # adder.sub set somewhere below
            ]
        with m.Elif(active_unit.branch):
            comb += [
                compare.funct3.eq(funct3),
                # Compare Unit uses Adder for carry and overflow flags.
                adder.src1.eq(rs1val),
                adder.src2.eq(rs2val),
                # adder.sub set somewhere below
            ]
        with m.Elif(active_unit.csr):
            comb += [
                csr_unit.func3.eq(funct3),
                csr_unit.csr_idx.eq(csr_idx),
                csr_unit.rs1.eq(rs1),
                csr_unit.rs1val.eq(rs1val),
                csr_unit.rd.eq(rd),
                csr_unit.en.eq(1),
            ]

        comb += [
            compare.negative.eq(adder.res[-1]),
            compare.overflow.eq(adder.overflow),
            compare.carry.eq(adder.carry),
            compare.zero.eq(adder.res == 0),
        ]

        # Decoding state (with redundancy - instr. type not known yet).
        # We use 'ibus.read_data' instead of 'instr' (that is driven by sync domain)
        # for getting registers to save 1 cycle.
        comb += [
            opcode.eq(instr[0:7]),
            rd.eq(instr[7:12]),
            funct3.eq(instr[12:15]),
            rs1.eq(instr[15:20]),
            rs2.eq(instr[20:25]),
            funct7.eq(instr[25:32]),
        ]

        def trap(cause: Optional[Union[TrapCause, IrqCause]], interrupt=False):
            m.d.sync += active_unit.eq(0)
            m.next = "TRAP"

            if cause is None:
                return
            assert isinstance(cause, TrapCause) or isinstance(cause, IrqCause) 
            e = exception_unit
            notifiers = e.irq_cause_map if interrupt else e.trap_cause_map 
            m.d.comb += notifiers[cause].eq(1)

        self.fetch = Signal()
        interconnect_error = self.interconnect_error = Signal()
        comb += interconnect_error.eq(
            exception_unit.m_store_error
            | exception_unit.m_fetch_error
            | exception_unit.m_load_error
        )

        def fetch_with_new_pc(pc : Signal):
            m.next = "FETCH"
            m.d.sync += self.pc.eq(pc)
            m.d.sync += active_unit.eq(0)

        with m.If(~self.running_state.halted):
            with m.FSM() as self.main_fsm:
                with m.State("FETCH"):
                    """
                    TODO
                    Timer interrupts are disbled for now, as whole CPU halting mechainsm
                    needs rethinking.
                    """
                    # trap(IrqCause.M_TIMER_INTERRUPT, interrupt=True)
                    with m.If(self.running_state_interface.haltreq):
                        sync += [
                            self.running_state.halted.eq(1),
                        ]
                    with m.Else():
                        with m.If(pc & 0b11):
                            trap(TrapCause.FETCH_MISALIGNED)
                        with m.Else():
                            comb += [
                                ibus.en.eq(1),
                                ibus.store.eq(0),
                                ibus.addr.eq(pc),
                                ibus.mask.eq(0b1111),
                                ibus.is_fetch.eq(1),
                            ]
                        with m.If(interconnect_error):
                            trap(cause=None)
                        with m.If(ibus.ack):
                            sync += [
                                instr.eq(ibus.read_data),
                            ]
                            m.next = "DECODE"
                with m.State("DECODE"):
                    comb += self.fetch.eq(1) # only for simulation, notify that 'instr' ready to use.
                    m.next = "EXECUTE"
                    # here, we have registers already fetched into rs1val, rs2val.
                    with m.If(instr & 0b11 != 0b11):
                        trap(TrapCause.ILLEGAL_INSTRUCTION)
                    with m.If(match_logic_unit(opcode, funct3, funct7)):
                        sync += [
                            active_unit.logic.eq(1),
                        ]
                    with m.Elif(match_adder_unit(opcode, funct3, funct7)):
                        sync += [
                            active_unit.adder.eq(1),
                            adder.sub.eq(
                                (opcode == InstrType.ALU) & (funct7 == Funct7.SUB)
                            ),
                        ]
                    with m.Elif(match_shifter_unit(opcode, funct3, funct7)):
                        sync += [
                            active_unit.shifter.eq(1),
                        ]
                    with m.Elif(match_loadstore_unit(opcode, funct3, funct7)):
                        sync += [
                            active_unit.mem_unit.eq(1),
                        ]
                    with m.Elif(match_compare_unit(opcode, funct3, funct7)):
                        sync += [
                            active_unit.compare.eq(1),
                            adder.sub.eq(1),
                        ]
                    with m.Elif(match_lui(opcode, funct3, funct7)):
                        sync += [
                            active_unit.lui.eq(1),
                        ]
                        comb += [
                            reg_read_port1.addr.eq(rd),
                            # rd will be available in next cycle in rs1val
                        ]
                    with m.Elif(match_auipc(opcode, funct3, funct7)):
                        sync += [
                            active_unit.auipc.eq(1),
                        ]
                    with m.Elif(match_jal(opcode, funct3, funct7)):
                        sync += [
                            active_unit.jal.eq(1),
                        ]
                    with m.Elif(match_jalr(opcode, funct3, funct7)):
                        sync += [
                            active_unit.jalr.eq(1),
                        ]
                    with m.Elif(match_branch(opcode, funct3, funct7)):
                        sync += [
                            active_unit.branch.eq(1),
                            adder.sub.eq(1),
                        ]
                    with m.Elif(match_csr(opcode, funct3, funct7)):
                        sync += [
                            active_unit.csr.eq(1)
                        ]
                    with m.Elif(match_mret(opcode, funct3, funct7)):
                        sync += [
                            active_unit.mret.eq(1)
                        ]
                    with m.Elif(match_sfence_vma(opcode, funct3, funct7)):
                        pass # sfence.vma
                    with m.Elif(opcode == 0b0001111):
                        pass # fence
                    with m.Else():
                        trap(TrapCause.ILLEGAL_INSTRUCTION)
                with m.State("EXECUTE"):
                    with m.If(active_unit.logic):
                        sync += [
                            rdval.eq(logic.res),
                        ]
                    with m.Elif(active_unit.adder):
                        sync += [
                            rdval.eq(adder.res),
                        ]
                    with m.Elif(active_unit.shifter):
                        sync += [
                            rdval.eq(shifter.res),
                        ]
                    with m.Elif(active_unit.mem_unit):
                        sync += [
                            rdval.eq(mem_unit.res),
                        ]
                    with m.Elif(active_unit.compare):
                        sync += [
                            rdval.eq(compare.condition_met),
                        ]
                    with m.Elif(active_unit.lui):
                        sync += [
                            rdval.eq(Cat(Const(0, 12), uimm)),
                        ]
                    with m.Elif(active_unit.auipc):
                        sync += [
                            rdval.eq(pc + Cat(Const(0, 12), uimm)),
                        ]
                    with m.Elif(active_unit.jal | active_unit.jalr):
                        sync += [
                            rdval.eq(pc + 4),
                        ]
                    with m.Elif(active_unit.csr):
                        sync += [
                            rdval.eq(csr_unit.rd_val)
                        ]

                    # control flow mux - all traps need to be here, otherwise it will overwrite m.next statement.
                    with m.If(active_unit.mem_unit):
                        with m.If(mem_unit.ack):
                            m.next = "WRITEBACK"
                            sync += active_unit.eq(0)
                        with m.Else():
                            m.next = "EXECUTE"
                        with m.If(interconnect_error):
                            # NOTE: 
                            # the order of that 'If' is important.
                            # In case of error overwrite m.next above.
                            trap(cause=None)
                    with m.Elif(active_unit.csr):
                        with m.If(csr_unit.illegal_insn):
                            trap(TrapCause.ILLEGAL_INSTRUCTION)
                        with m.Else():
                            with m.If(csr_unit.vld):
                                m.next = "WRITEBACK"
                                sync += active_unit.eq(0)
                            with m.Else():
                                m.next = "EXECUTE"
                    with m.Elif(active_unit.mret):
                        comb += exception_unit.m_mret.eq(1)
                        fetch_with_new_pc(exception_unit.mepc)
                    with m.Else():
                        # all units not specified by default take 1 cycle
                        m.next = "WRITEBACK"
                        sync += active_unit.eq(0)

                    jal_offset = Signal(signed(21))
                    comb += jal_offset.eq(
                        Cat(
                            Const(0, 1),
                            instr[21:31],
                            instr[20],
                            instr[12:20],
                            instr[31],
                        ).as_signed()
                    )
                    
                    pc_addend = Signal(signed(32))
                    sync += pc_addend.eq(
                        Mux(active_unit.jal, jal_offset, 4)
                    )

                    branch_addend = Signal(signed(13))
                    comb += branch_addend.eq(
                        Cat(
                            Const(0, 1),
                            instr[8:12],
                            instr[25:31],
                            instr[7],
                            instr[31],
                        ).as_signed() # TODO is it ok that it's signed?
                    )

                    with m.If(active_unit.branch):
                        with m.If(compare.condition_met):
                            sync += pc_addend.eq(branch_addend)

                    new_pc = Signal(32)
                    is_jalr_latch = Signal() # that's bad workaround
                    with m.If(active_unit.jalr):
                        sync += is_jalr_latch.eq(1)
                        sync += new_pc.eq(rs1val.as_signed() + imm)
                
                with m.State("WRITEBACK"):
                    with m.If(is_jalr_latch):
                        sync += pc.eq(new_pc)
                    with m.Else():
                        sync += pc.eq(pc + pc_addend)
                    sync += is_jalr_latch.eq(0)

                    # Here, rdval is already calculated. If neccessary, put it into register file.
                    should_write_rd = self.should_write_rd = Signal()
                    writeback = self.writeback = Signal()
                    # for riscv-dv simulation:
                    # detect that instruction does not perform register write to avoid infinite loop
                    # by checking writeback & should_write_rd
                    # TODO it will break for trap-causing instructions.
                    comb += writeback.eq(1)
                    comb += should_write_rd.eq(
                        reduce(
                            or_,
                            [
                                match_shifter_unit(opcode, funct3, funct7),
                                match_adder_unit(opcode, funct3, funct7),
                                match_logic_unit(opcode, funct3, funct7),
                                match_load(opcode, funct3, funct7),
                                match_compare_unit(opcode, funct3, funct7),
                                match_lui(opcode, funct3, funct7),
                                match_auipc(opcode, funct3, funct7),
                                match_jal(opcode, funct3, funct7),
                                match_jalr(opcode, funct3, funct7),
                                match_csr(opcode, funct3, funct7),
                            ],
                        )
                        & (rd != 0)
                    )

                    with m.If(should_write_rd):
                        comb += reg_write_port.en.eq(True)
                    m.next = "FETCH"

                with m.State("TRAP"):
                    """
                    NOTE: First implementation didn't have TRAP state. It was added to fix ibus issue,
                    as there were situations that the ibus.en was high 100% time (e.g. trap and fetch from non-existing mtvec),
                    so that the debug bus couldn't own the bus.
                    """
                    fetch_with_new_pc(Cat(Const(0, 2), self.csr_unit.mtvec.base))
            
        return m
