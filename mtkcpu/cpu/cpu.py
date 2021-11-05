#!/usr/bin/env python3
from __future__ import with_statement
from enum import Enum
from functools import reduce
from operator import or_

from nmigen import Mux, Cat, Signal, Const, Record, Elaboratable, Module, Memory, signed
from nmigen.hdl.rec import Layout

from mtkcpu.utils.common import CODE_START_ADDR
from mtkcpu.units.adder import AdderUnit, match_adder_unit
from mtkcpu.units.compare import CompareUnit, match_compare_unit
from mtkcpu.units.loadstore import (InterfaceToWishboneMasterBridge, MemoryArbiter, MemoryUnit,
                                    match_load, match_loadstore_unit)
from mtkcpu.units.logic import LogicUnit, match_logic_unit
from mtkcpu.units.rvficon import RVFIController, rvfi_layout
from mtkcpu.units.shifter import ShifterUnit, match_shifter_unit
from mtkcpu.units.upper import match_auipc, match_lui
from mtkcpu.utils.common import matcher
from mtkcpu.utils.isa import Funct3, InstrType, Funct7
from mtkcpu.units.debug.jtag import JTAGTap
from mtkcpu.units.debug.top import DebugUnit

MEM_WORDS = 10


class Error(Enum):
    OK = 0
    OP_CODE = 1
    MISALIGNED_INSTR = 2
    WRONG_INSTR = 3


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
            ]
        )


class ActiveUnit(Record):
    def __init__(self):
        super().__init__(ActiveUnitLayout(), name="active_unit")


class MtkCpu(Elaboratable):
    def __init__(self, reg_init=[0 for _ in range(32)], with_rvfi=False, with_debug=True, mem_config=None):

        if len(reg_init) > 32:
            raise ValueError(
                f"Register init length (={len(reg_init)}) exceedes 32!"
            )

        if reg_init[0] != 0:
            print(
                f"WARNING, register x0 set to value {reg_init[0]}, however it will be overriden with zero (due to RiscV spec).."
            )
            reg_init[0] = 0

        if not mem_config:
            raise ValueError("mem_config must be passed! legacy note: previously memory simulation used custom model, "
            "at some point we started taking advantage of nMigen's 'Memory' class simulation model.")
        self.mem_config = mem_config

        self.with_rvfi = with_rvfi

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

        self.err = Signal(Error, reset=Error.OK)

        self.DEBUG_CTR = Signal(32)

        self.halt = Signal()

        self.gprf_debug_addr = Signal(32)
        self.gprf_debug_data = Signal(32)
        self.gprf_debug_write_en = Signal()

        self.TRAP_ADDR = 0xAAA0

    def elaborate(self, platform):
        self.m = m = Module()

        comb = m.d.comb
        sync = m.d.sync

        # Memory interface.
        arbiter = self.arbiter = m.submodules.arbiter = MemoryArbiter(mem_config=self.mem_config)

        ibus = arbiter.port(priority=2)

        if self.with_rvfi:
            rvficon = m.submodules.rvficon = RVFIController() # NOQA
            self.rvfi = Record(rvfi_layout)

        if self.with_debug:
            m.submodules.debug = self.debug = DebugUnit(self)
            self.debug_bus = arbiter.port(priority=1)

        sync += self.DEBUG_CTR.eq(self.DEBUG_CTR + 1)


        # CPU units used.
        logic = m.submodules.logic = LogicUnit()
        adder = m.submodules.adder = AdderUnit()
        shifter = m.submodules.shifter = ShifterUnit()
        mem_unit = m.submodules.mem_unit = MemoryUnit(
            mem_port=arbiter.port(priority=0)
        )
        compare = m.submodules.compare = CompareUnit()

        # Current decoding state signals.
        instr = Signal(32)
        funct3 = Signal(3)
        funct7 = Signal(7)
        rd = Signal(5)
        rs1 = Signal(5)
        rs2 = Signal(5)
        rs1val = Signal(32)
        rs2val = Signal(32)
        rdval = Signal(32)  # calculated by unit, stored to register file
        imm = Signal(signed(12))
        uimm = Signal(20)
        opcode = Signal(InstrType)

        # Register file. Contains two read ports (for rs1, rs2) and one write port.
        regs = Memory(width=32, depth=32, init=self.reg_init)
        reg_read_port1 = m.submodules.reg_read_port1 = regs.read_port()
        reg_read_port2 = m.submodules.reg_read_port2 = regs.read_port()
        reg_write_port = (
            self.reg_write_port
        ) = m.submodules.reg_write_port = regs.write_port()


        # DebugModule is able to read and write GPR values.
        if self.with_debug:
            comb += self.halt.eq(self.debug.HALT)
        else:
            comb += self.halt.eq(0)

        with m.If(self.halt):
            comb += [
                reg_read_port1.addr.eq(self.gprf_debug_addr),
                reg_write_port.addr.eq(self.gprf_debug_addr),
                reg_write_port.en.eq(self.gprf_debug_write_en)
            ]

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
                # reg_write_port.en set later

                rs1val.eq(reg_read_port1.data),
                rs2val.eq(reg_read_port2.data),
            ]

        pc = self.pc = Signal(32, reset=CODE_START_ADDR)

        # assert ( popcount(active_unit) in [0, 1] )
        active_unit = ActiveUnit()

        # this is not true for all instrutions, but in specific cases will be overwritten later
        comb += [
            imm.eq(instr[20:32]),
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
                shifter.src1.eq(rs1val),
                shifter.shift.eq(
                    Mux(
                        opcode == InstrType.OP_IMM, imm[0:5], rs2val[0:5]
                    )  # TODO check semantics
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

        self.EBREAK = Signal()
        self.FENCE = Signal()

        sync += self.EBREAK.eq(0)
        sync += self.FENCE.eq(0)

        with m.FSM():
            with m.State("FETCH"):
                with m.If(pc & 0b11):
                    comb += self.err.eq(Error.MISALIGNED_INSTR)
                    m.next = "FETCH"  # loop
                with m.Else():
                    sync += [
                        ibus.en.eq(1),
                        ibus.store.eq(0),
                        ibus.addr.eq(pc),
                        ibus.mask.eq(0b1111),
                    ]
                    with m.If(ibus.en & ~ibus.busy):
                        m.next = "WAIT_FETCH"
                    with m.Else():
                        m.next = "FETCH"
            with m.State("WAIT_FETCH"):
                with m.If(ibus.ack):
                    sync += [
                        instr.eq(ibus.read_data),
                        ibus.en.eq(0),
                    ]
                    m.next = "DECODE"
                with m.Else():
                    m.next = "WAIT_FETCH"
            with m.State("DECODE"):
                # here, we have registers already fetched into rs1val, rs2val.
                with m.If(instr & 0b11 != 0b11):
                    comb += self.err.eq(Error.OP_CODE)
                    m.next = "DECODE"  # loop TODO

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
                with m.Elif(opcode == 0b1110011):
                    # EBREAK/ECALL
                    sync += self.EBREAK.eq(1)
                with m.Elif(opcode == 0b0001111):
                    # FENCE
                    sync += self.FENCE.eq(1)
                with m.Else():
                    # wrong instruction code:
                    # set proper mcause and jump intro trap
                    m.next = "FETCH"
                    comb += self.err.eq(Error.WRONG_INSTR)
                    sync += self.pc.eq(self.TRAP_ADDR)
                m.next = "EXECUTE"
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
                        rdval.eq(
                            (rs1val & 0x0000_0FFF) | Cat(Const(0, 12), uimm)
                        ),
                    ]
                with m.Elif(active_unit.auipc):
                    sync += [
                        rdval.eq(pc + Cat(Const(0, 12), uimm)),
                    ]
                with m.Elif(active_unit.jal | active_unit.jalr):
                    sync += [
                        rdval.eq(pc + 4),
                    ]
                # with m.Elif(active_unit.branch):
                #     pass

                with m.If(active_unit.mem_unit):
                    with m.If(mem_unit.ack):
                        m.next = "WRITEBACK"
                        sync += active_unit.eq(0)
                    with m.Else():
                        m.next = "EXECUTE"
                with m.Else():
                    # all units not specified by default take 1 cycle
                    m.next = "WRITEBACK"
                    sync += active_unit.eq(0)

                pc_offset = Signal(signed(32))
                comb += pc_offset.eq(
                    Mux(
                        active_unit.jal,
                        Cat(
                            Const(0, 1),
                            instr[21:31],
                            instr[20],
                            instr[12:20],
                            instr[31],
                        ),
                        rs1val + imm,
                    )
                )
                pc_addend = Signal(signed(32))
                sync += pc_addend.eq(
                    Mux(active_unit.jal | active_unit.jalr, pc_offset, 4)
                )

                branch_addend = Signal(signed(13))
                comb += branch_addend.eq(
                    Cat(
                        Const(0, 1),
                        instr[8:12],
                        instr[25:31],
                        instr[7],
                        instr[31],
                    )
                )

                with m.If(active_unit.branch):
                    with m.If(compare.condition_met):
                        sync += pc_addend.eq(branch_addend)

            with m.State("WRITEBACK"):
                sync += pc.eq(pc + pc_addend)

                # Here, rdval is already calculated. If neccessary, put it into register file.
                should_write_rd = (
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
                        ],
                    )
                    & (rd != 0)
                )

                with m.If(should_write_rd):
                    comb += reg_write_port.en.eq(True)
                m.next = "FETCH"

        # TODO
        # That piece of code comes from minerva CPU, for now it's only copy-pasted.
        # Let's make it work.
        # if self.with_rvfi:
        #     cpu.d.comb += [
        #         rvficon.d_insn.eq(decoder.instruction),
        #         rvficon.d_rs1_addr.eq(Mux(decoder.rs1_re, decoder.rs1, 0)),
        #         rvficon.d_rs2_addr.eq(Mux(decoder.rs2_re, decoder.rs2, 0)),
        #         rvficon.d_rs1_rdata.eq(Mux(decoder.rs1_re, d_src1, 0)),
        #         rvficon.d_rs2_rdata.eq(Mux(decoder.rs2_re, d_src2, 0)),
        #         rvficon.d_stall.eq(d.stall),
        #         rvficon.x_mem_addr.eq(loadstore.x_addr[2:] << 2),
        #         rvficon.x_mem_wmask.eq(
        #             Mux(loadstore.x_store, loadstore.x_mask, 0)
        #         ),
        #         rvficon.x_mem_rmask.eq(
        #             Mux(loadstore.x_load, loadstore.x_mask, 0)
        #         ),
        #         rvficon.x_mem_wdata.eq(loadstore.x_store_data),
        #         rvficon.x_stall.eq(x.stall),
        #         rvficon.m_mem_rdata.eq(loadstore.m_load_data),
        #         rvficon.m_fetch_misaligned.eq(exception.m_fetch_misaligned),
        #         rvficon.m_illegal_insn.eq(m.sink.illegal),
        #         rvficon.m_load_misaligned.eq(exception.m_load_misaligned),
        #         rvficon.m_store_misaligned.eq(exception.m_store_misaligned),
        #         rvficon.m_exception.eq(exception.m_raise),
        #         rvficon.m_mret.eq(m.sink.mret),
        #         rvficon.m_branch_taken.eq(m.sink.branch_taken),
        #         rvficon.m_branch_target.eq(m.sink.branch_target),
        #         rvficon.m_pc_rdata.eq(m.sink.pc),
        #         rvficon.m_stall.eq(m.stall),
        #         rvficon.m_valid.eq(m.valid),
        #         rvficon.w_rd_addr.eq(Mux(gprf_wp.en, gprf_wp.addr, 0)),
        #         rvficon.w_rd_wdata.eq(Mux(gprf_wp.en, gprf_wp.data, 0)),
        #         rvficon.mtvec_r_base.eq(exception.mtvec.r.base),
        #         rvficon.mepc_r_value.eq(exception.mepc.r),
        #         rvficon.rvfi.connect(self.rvfi),
        #     ]

        return m
