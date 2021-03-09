#!/usr/bin/env python3
from nmigen import *
from enum import Enum

START_ADDR = 0 # 0x1000
MEM_WORDS = 10

class Error(Enum):
    OK = 0
    OP_CODE = 1
    MISALIGNED_INSTR = 2

class InstrType(Enum):
    LOAD = 0b00000
    STORE = 0b01000
    ADD = 0b10000
    SUB = 0b10001
    BRANCH = 0b11000
    JAL = 0b11001
    AUIPC = 0b00101
    LUI = 0b01101
    OP_IMM = 0b00100

class InstrFormat(Enum):
    R = 0 # addw t0, t1, t2
    I = 1 # addi t1, t0, 100
    S = 2 # sw t1, 8(t2)  # no destination register
    B = 3 # beq t1, t2, End # no destination register
    U = 4
    J = 5

from units.loadstore import LoadStoreUnit

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

        mem = m.submodules.mem = LoadStoreUnit(32, mem_init=self.mem_init)

        # regs = Memory(width=self.width, depth=32, init=[0 for _ in range(32)])

        pc = Signal(32, reset=START_ADDR)

        # current state signals.
        instr = Signal(32)
        opcode = Signal(5)
        op_type = Signal(InstrType)
        comb += [
            opcode.eq(instr[2:8]),
            op_type.eq(opcode),
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
                    sync += instr.eq(mem.read_data)
                    m.next = "DECODE"
                with m.Else():
                    m.next = "WAIT_FETCH"
            with m.State("DECODE"):
                with m.If(instr & 0b11 != 0b11):
                    comb += self.err.eq(Error.OP_CODE)
                    m.next = "DECODE" # loop
                sync += pc.eq(pc + 4)
                m.next = "FETCH"
                # funct3 = Signal(3)
                # funct7 = Signal(7)
                
                # comb += op_type.eq()
                

        return m



if __name__ == "__main__":
    from nmigen.back.pysim import *

    from asm_dump import dump_asm
    from io import StringIO

    source_file = StringIO(
    """
    .section code
        lw t0, 0(t1)
        li t1, 0xdeadbeef
    """
    )
    
    m = MtkCpu(mem_init=dump_asm(source_file))

    sim = Simulator(m)
    sim.add_clock(1e-6) # 1 mhz?

    def test():
        for _ in range(20):
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