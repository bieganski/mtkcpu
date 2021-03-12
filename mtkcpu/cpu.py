#!/usr/bin/env python3
from nmigen import *
from enum import Enum
from nmigen.hdl.rec import * # Record, Layout

START_ADDR = 0 # 0x1000
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


class ActiveUnitLayout(Layout):
    def __init__(self):
        super().__init__([
            ("logic", 1),
            ("adder", 1),
            ("dxdt", 1),
        ])

class ActiveUnit(Record):
    def __init__(self):
        super().__init__(ActiveUnitLayout(), name="active_unit")



class MtkCpu(Elaboratable):
    def __init__(self, mem_init=[0 for _ in range(MEM_WORDS)]):

        if len(mem_init) > MEM_WORDS:
            raise ValueError(f"Memory init length exceedes memory size! it's max length is {MEM_WORDS}, passed: {len(mem_init)}.")

        # 0xDE for debugging (uninitialized data magic byte)
        self.mem_init = mem_init + [0xDE] * (len(mem_init) - MEM_WORDS)

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

        # Memory interface.
        mem = m.submodules.mem = LoadStoreUnit(32, mem_init=self.mem_init)

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
        opcode = Signal(InstrType)

        # Register file. Contains two read ports (for rs1, rs2) and one write port. 
        regs = Memory(width=32, depth=32, init=[i for i in range(32)])
        reg_read_port1 = m.submodules.reg_read_port1 = regs.read_port()
        reg_read_port2 = m.submodules.reg_read_port2 = regs.read_port()
        reg_write_port = m.submodules.reg_write_port = regs.write_port()
        
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

        # drive input signals of actually used unit.
        with m.If(active_unit.logic):
            comb += [
                logic.src1.eq(rs1val),
                logic.src2.eq(rs2val),
            ]
        with m.Elif(active_unit.adder):
            comb += [
                adder.src1.eq(rs1val),
                adder.src2.eq(rs2val),
            ]


        # Decoding state (with redundancy - unknown instr. type).     
        # We use mem.read_data instead of instr for getting registers to save 1 cycle.           
        comb += [
            opcode.eq(instr[0:7]),
            rd.eq(mem.read_data[7:12]),
            funct3.eq(instr[12:15]),
            rs1.eq(mem.read_data[15:20]),
            rs2.eq(mem.read_data[20:25]),
            funct7.eq(instr[25:32]),
        ]

        # Integer computational instructions are either encoded as register-immediate operations using
        #    the I-type format or as register-register operations using the R-type format.
        with m.FSM() as fsm:
            with m.State("FETCH"):
                with m.If(pc & 0b11):
                    comb += self.err.eq(Error.MISALIGNED_INSTR)
                    m.next = "FETCH" # loop
                with m.Else(): # TODO remove that 'else'
                    comb += [
                        mem.read_addr.eq(pc >> 2),
                        mem.read_rdy.eq(True) # important! only one cycle set
                    ]
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
                with m.Switch(opcode):
                    with m.Case(InstrType.ALU):
                        with m.If(match_logic_unit(opcode, funct3, funct7)):
                            sync += [
                                active_unit.logic.eq(1),
                            ]
                        with m.Elif(match_adder_unit(opcode, funct3, funct7)):
                            sync += [
                                active_unit.adder.eq(1),
                                adder.sub.eq(funct7 == Funct7.SUB),
                            ]
                m.next = "EXECUTE" # TODO assumption: single-cycle execution, may not be true for mul/div etc.
            with m.State("EXECUTE"):
                # instr. is being executed in specified unit
                with m.If(active_unit.logic):
                    sync += [
                        active_unit.logic.eq(0),
                        rdval.eq(logic.res),
                    ]
                with m.Elif(active_unit.adder):
                    sync += [
                        active_unit.adder.eq(0),
                        rdval.eq(adder.res),
                    ]
                m.next = "STORE"
            with m.State("STORE"):
                # Here, rdval is present. If neccessary, put it into register file.
                should_write_rd = ((opcode == InstrType.ALU) | (opcode == InstrType.LOAD)) # TODO

                with m.If(should_write_rd):
                    comb += reg_write_port.en.eq(True)
                m.next = "FETCH"
                        

                

        return m



if __name__ == "__main__":
    from nmigen.back.pysim import *

    from asm_dump import dump_asm
    from io import StringIO

    source_file = StringIO(
    """
    .section code
        add x1, x2, x3
        lw t0, 0(t1)
        li t1, 0xdeadbeef
    """
    )
    
    m = MtkCpu(mem_init=dump_asm(source_file))

    sim = Simulator(m)
    sim.add_clock(1e-6) # 1 mhz?

    def test():
        for _ in range(50):
            yield
    sim.add_sync_process(test)
    with sim.write_vcd("cpu.vcd"):
        sim.run()
        print("simulation done!")




# if __name__ == "__main__":
#     from minized import MinizedPlatform, TopWrapper
#     m = MtkCpu(32)
#     MinizedPlatform().build(TopWrapper(m), do_program=False)

# exit(0)