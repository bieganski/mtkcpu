#!/usr/bin/env python3
from nmigen import *
from enum import Enum

START_ADDR = 0 # 0x1000
MEM_WORDS = 10

class Error(Enum):
    OK = 0
    OP_CODE = 1
    MISALIGNED_INSTR = 2

class MtkCpu(Elaboratable):
    def __init__(self, xlen, mem_init=[0 for _ in range(MEM_WORDS)]):

        if len(mem_init) > MEM_WORDS:
            raise ValueError(f"Memory init length exceedes memory size! it's max length is {MEM_WORDS}, passed: {len(mem_init)}.")

        mem_init = mem_init + [0]

        self.width = xlen
        self.mem_init = mem_init

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

        mem = Memory(width=self.width, depth=MEM_WORDS, init=self.mem_init)

        # regs = Memory(width=self.width, depth=32, init=[0 for _ in range(32)])

        read_port = m.submodules.read_port = mem.read_port()

        read_addr = Signal(range(MEM_WORDS * self.width))
        read_data = Signal(self.width)

        pc = Signal(self.width, reset=START_ADDR)

        # read_en = Signal(reset=True)
        # m.d.sync += read_en.eq(1 - read_en)

        comb += [
            read_port.addr.eq(read_addr),
            read_data.eq(read_port.data),
        ]

        write_port = m.submodules.write_port = mem.write_port()

        write_addr = Signal(range(MEM_WORDS * self.width))
        write_data = Signal(self.width)
        write_en = Signal(reset=False)

        comb += [
            write_port.addr.eq(write_addr),
            write_port.data.eq(write_data),
            write_port.en.eq(write_en),
        ]

        # sync += [
        #     write_en.eq(1 - write_en),

        #     read_addr.eq(read_addr + 1),
        #     write_data.eq(0x100 + write_addr),
        #     write_addr.eq(write_addr + 1),
        # ]

        instr = Signal(self.width)

        with m.FSM() as fsm:
            with m.State("FETCH"):
                with m.If(pc & 0b11):
                    comb += self.err.eq(Error.MISALIGNED_INSTR)
                    m.next = "FETCH" # loop
                comb += [
                    read_addr.eq(pc),
                ]
                m.next = "DECODE"
            with m.State("DECODE"):
                comb += [
                    instr.eq(read_data)
                ]
                with m.If(instr & 0b11 != 0b11):
                    comb += self.err.eq(Error.OP_CODE)
                    m.next = "DECODE" # loop
                
                

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
    
    m = MtkCpu(32, mem_init=dump_asm(source_file))

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