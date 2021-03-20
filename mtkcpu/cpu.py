#!/usr/bin/env python3
from nmigen import *
from enum import Enum
from nmigen.hdl.rec import * # Record, Layout
from operator import or_
from functools import reduce

START_ADDR = 0x1000
MEM_WORDS = 10

class Error(Enum):
    OK = 0
    OP_CODE = 1
    MISALIGNED_INSTR = 2
    AAAA = 3
    BBBB = 4

from isa import *
from units.loadstore import LoadStoreUnit
from units.logic import LogicUnit, match_logic_unit
from units.adder import AdderUnit, match_adder_unit
from units.shifter import ShifterUnit, match_shifter_unit


class ActiveUnitLayout(Layout):
    def __init__(self):
        super().__init__([
            ("logic", 1),
            ("adder", 1),
            ("shifter", 1),
        ])

class ActiveUnit(Record):
    def __init__(self):
        super().__init__(ActiveUnitLayout(), name="active_unit")



class MtkCpu(Elaboratable):
    def __init__(self, reg_init=[0 for _ in range(32)], mem_init=[0 for _ in range(MEM_WORDS)]):

        if len(mem_init) > MEM_WORDS:
            raise ValueError(f"Memory init length exceedes memory size! it's max length is {MEM_WORDS}, passed: {len(mem_init)}.")
        if len(reg_init) > 32:
            raise ValueError(f"Register init length (={len(reg_init)}) exceedes 32!")

        if reg_init[0] != 0:
            print(f"WARNING, register x0 set to value {reg_init[0]}, however it will be overriden with zero..")
        reg_init[0] = 0

        # 0xDE for debugging (uninitialized data magic byte)
        self.mem_init = mem_init + [0xDE] * (len(mem_init) - MEM_WORDS)
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

    def elaborate(self, platform):
        m = Module()

        comb = m.d.comb
        sync = m.d.sync

        # CPU units used.
        logic = m.submodules.logic = LogicUnit()
        adder = m.submodules.adder = AdderUnit()
        shifter = m.submodules.shifter = ShifterUnit()

        # Memory interface.
        mem = self.mem = m.submodules.mem = LoadStoreUnit(32, mem_init=self.mem_init)

        # Current decoding state signals.
        instr = Signal(32)
        funct3 = Signal(3)
        funct7 = Signal(7)
        rd = Signal(5)
        rs1 = Signal(5)
        rs2 = Signal(5)
        rs1val = Signal(32)
        rs2val = Signal(32)
        rdval = Signal(32)
        imm = Signal(12)
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

        # Decoding state (with redundancy - instr. type not known yet).     
        # We use mem.read_data instead of instr for getting registers to save 1 cycle.           
        comb += [
            opcode.eq(instr[0:7]),
            rd.eq(mem.read_data[7:12]),
            funct3.eq(instr[12:15]),
            rs1.eq(mem.read_data[15:20]),
            rs2.eq(mem.read_data[20:25]),
            funct7.eq(instr[25:32]),
        ]

        with m.FSM() as fsm:
            with m.State("FETCH"):
                with m.If(pc & 0b11):
                    comb += self.err.eq(Error.MISALIGNED_INSTR)
                    m.next = "FETCH" # loop
                with m.Else(): # TODO remove that 'else'
                    comb += [
                        mem.read_addr.eq(pc),
                        mem.read_rdy.eq(True) # important! only one cycle set
                    ]
                with m.If(mem.read_vld):
                    m.next = "WAIT_FETCH"
            with m.State("WAIT_FETCH"):
                with m.If(mem.read_done):
                    sync += [
                        instr.eq(mem.read_data),
                    ]
                    m.next = "DECODE"
                with m.Else():
                    m.next = "WAIT_FETCH"
            with m.State("DECODE"):
                # here, we have registers already fetched into rs1val, rs2val.
                with m.If(instr & 0b11 != 0b11):
                    comb += self.err.eq(Error.OP_CODE)
                    m.next = "DECODE" # loop TODO
                sync += pc.eq(pc + 4)

                # comb += self.err.eq(Error.BBBB)
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
                m.next = "EXECUTE" # TODO assumption: single-cycle execution, may not be true for mul/div etc.
            with m.State("EXECUTE"):
                # instr. is being executed in specified unit
                sync += active_unit.eq(0)
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
                m.next = "STORE"
            with m.State("STORE"):
                # Here, rdval is present. If neccessary, put it into register file.

                # TODO rather have it by checking instr type (R, J etc.)
                should_write_rd = reduce(or_,
                    [
                        match_shifter_unit(opcode, funct3, funct7),
                        match_adder_unit(opcode, funct3, funct7),
                        match_logic_unit(opcode, funct3, funct7),
                    ]
                ) & (rd != 0)

                with m.If(should_write_rd):
                    comb += reg_write_port.en.eq(True)
                m.next = "FETCH"
        
        return m

