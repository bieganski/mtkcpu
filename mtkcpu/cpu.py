#!/usr/bin/env python3
from nmigen import *
from enum import Enum
from nmigen.hdl.rec import * # Record, Layout
from operator import or_
from functools import reduce
from common import START_ADDR

MEM_WORDS = 10

class Error(Enum):
    OK = 0
    OP_CODE = 1
    MISALIGNED_INSTR = 2
    AAAA = 3
    BBBB = 4

from isa import *
from units.loadstore import LoadStoreUnit, MemoryUnit, MemoryArbiter, match_load, match_loadstore_unit
from units.logic import LogicUnit, match_logic_unit
from units.adder import AdderUnit, match_adder_unit
from units.shifter import ShifterUnit, match_shifter_unit
from units.compare import CompareUnit, match_compare_unit
from units.upper import match_lui, match_auipc


class ActiveUnitLayout(Layout):
    def __init__(self):
        super().__init__([
            ("logic", 1),
            ("adder", 1),
            ("shifter", 1),
            ("mem_unit", 1),
            ("compare", 1),
            ("lui", 1),
            ("auipc", 1),
        ])

class ActiveUnit(Record):
    def __init__(self):
        super().__init__(ActiveUnitLayout(), name="active_unit")



class MtkCpu(Elaboratable):
    def __init__(self, reg_init=[0 for _ in range(32)]):

        if len(reg_init) > 32:
            raise ValueError(f"Register init length (={len(reg_init)}) exceedes 32!")

        if reg_init[0] != 0:
            print(f"WARNING, register x0 set to value {reg_init[0]}, however it will be overriden with zero..")
        reg_init[0] = 0

        # 0xDE for debugging (uninitialized data magic byte)
        self.reg_init = reg_init + [0x0]  * (len(reg_init) - 32)

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

    def elaborate(self, platform):
        m = Module()

        comb = m.d.comb
        sync = m.d.sync

        sync += self.DEBUG_CTR.eq(self.DEBUG_CTR + 1)

        # Memory interface.
        arbiter = self.arbiter = m.submodules.arbiter = MemoryArbiter()

        ibus = self.ibus = m.submodules.ibus = LoadStoreUnit(mem_port=arbiter.port(priority=1))

        # CPU units used.
        logic = m.submodules.logic = LogicUnit()
        adder = m.submodules.adder = AdderUnit()
        shifter = m.submodules.shifter = ShifterUnit()
        mem_unit = m.submodules.mem_unit = MemoryUnit(mem_port=arbiter.port(priority=0))
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
        rdval = Signal(32) # calculated by unit, stored to register file
        rdval_lower = Signal(32) # fetched from register file, concatenated with upper 20 bit (lui)
        imm = Signal(signed(12))
        uimm = Signal(20)
        opcode = Signal(InstrType)

        # Register file. Contains two read ports (for rs1, rs2) and one write port. 
        regs = Memory(width=32, depth=32, init=self.reg_init)
        reg_read_port1 = m.submodules.reg_read_port1 = regs.read_port()
        reg_read_port2 = m.submodules.reg_read_port2 = regs.read_port()
        reg_write_port = self.reg_write_port = m.submodules.reg_write_port = regs.write_port()
        
        comb += [
            reg_read_port1.addr.eq(rs1),
            reg_read_port2.addr.eq(rs2),
            rs1val.eq(reg_read_port1.data),
            rs2val.eq(reg_read_port2.data),

            reg_write_port.addr.eq(rd),
            reg_write_port.data.eq(rdval),
            # reg_write_port.en set later
        ]
        # Additional register - program counter.
        pc = Signal(32, reset=START_ADDR)

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
                logic.src2.eq(Mux(
                    opcode == InstrType.OP_IMM,
                    imm,
                    rs2val
                )),
            ]
        with m.Elif(active_unit.adder):
            comb += [
                adder.src1.eq(rs1val),
                adder.src2.eq(Mux(
                    opcode == InstrType.OP_IMM,
                    imm,
                    rs2val
                )),
            ]
        with m.Elif(active_unit.shifter):
            comb += [
                shifter.funct3.eq(funct3),
                shifter.src1.eq(rs1val),
                shifter.shift.eq(Mux(
                    opcode == InstrType.OP_IMM, 
                    imm[0:5],
                    rs2val[0:5]) # TODO check semantics
                ),
            ]
        with m.Elif(active_unit.mem_unit):
            comb += [
                mem_unit.en.eq(1),
                mem_unit.funct3.eq(funct3),
                mem_unit.src1.eq(rs1val),
                mem_unit.src2.eq(rs2val),
                mem_unit.store.eq(opcode == InstrType.STORE),
                mem_unit.offset.eq(Mux(
                    opcode == InstrType.LOAD,
                    imm,
                    Cat(rd, imm[5:12])
                )),
            ]
        with m.Elif(active_unit.compare):
            comb += [
                compare.funct3.eq(funct3),
                compare.src1.eq(rs1val),
                compare.src2.eq(Mux(
                    opcode == InstrType.OP_IMM, 
                    imm,
                    rs2val)
                ),
            ]

        # Decoding state (with redundancy - instr. type not known yet).     
        # We use 'ibus.read_data' instead of instr for getting registers to save 1 cycle.           
        comb += [
            opcode.eq(  instr[0:7]),
            rd.eq(      instr[7:12]),
            funct3.eq(  instr[12:15]),
            rs1.eq(     instr[15:20]),
            rs2.eq(     instr[20:25]),
            funct7.eq(  instr[25:32]),
        ]

        with m.FSM() as fsm:
            with m.State("FETCH"):
                with m.If(pc & 0b11):
                    comb += self.err.eq(Error.MISALIGNED_INSTR)
                    m.next = "FETCH" # loop
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
                    m.next = "DECODE" # loop TODO

                with m.If(match_logic_unit(opcode, funct3, funct7)):
                    sync += [
                        active_unit.logic.eq(1),
                    ]
                with m.Elif(match_adder_unit(opcode, funct3, funct7)):
                    sync += [
                        active_unit.adder.eq(1),
                        adder.sub.eq((opcode == InstrType.ALU) & (funct7 == Funct7.SUB)),
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
                    ]
                with m.Elif(match_lui(opcode, funct3, funct7)):
                    sync += [
                        active_unit.lui.eq(1),
                    ]
                    comb += [
                        reg_read_port1.addr.eq(rd),
                        # res will be available in next cycle in rs1val
                    ]
                with m.Elif(match_auipc(opcode, funct3, funct7)):
                    sync += [
                        active_unit.auipc.eq(1),
                    ]
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
                        rdval.eq(
                            pc + Cat(Const(0, 12), uimm)
                        ),
                    ]

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
                    
            with m.State("WRITEBACK"):

                sync += pc.eq(pc + 4)

                # Here, rdval is already calculated. If neccessary, put it into register file.

                # TODO rather have it by checking instr type (R, J etc.)
                should_write_rd = reduce(or_,
                    [
                        match_shifter_unit(opcode, funct3, funct7),
                        match_adder_unit(opcode, funct3, funct7),
                        match_logic_unit(opcode, funct3, funct7),
                        match_load(opcode, funct3, funct7),
                        match_compare_unit(opcode, funct3, funct7),
                        match_lui(opcode, funct3, funct7),
                        match_auipc(opcode, funct3, funct7),
                    ]
                ) & (rd != 0)

                with m.If(should_write_rd):
                    comb += reg_write_port.en.eq(True)
                m.next = "FETCH"
        
        return m

