from nmigen import *
from enum import Enum

MEM_WORDS = 10

from nmigen import *
from nmigen.hdl.rec import *
from nmigen.lib.coding import *


bus_layout = [
    ("adr",   30, DIR_FANOUT), # addresses aligned to 4
    ("dat_w", 32, DIR_FANOUT),
    ("dat_r", 32, DIR_FANIN),
    ("sel",    4, DIR_FANOUT),
    ("cyc",    1, DIR_FANOUT),
    ("ack",    1, DIR_FANIN),
    ("we",    1, DIR_FANOUT),
]

class PriorityEncoder(Elaboratable):
    def __init__(self, width):
        self.width = width
        self.i = Signal(self.width)
        self.o = Signal(range(self.width))

        self.none = Signal()

    def elaborate(self, platform):
        m = Module()

        for k in reversed(range(self.width)):
            with m.If(self.i[k]):
                m.d.comb += self.o.eq(k)
        m.d.comb += self.none.eq(self.i == 0) # no requests

        return m

class MemoryArbiter(Elaboratable):
    def __init__(self):
        self.ports = {}
        self.bus = Record(bus_layout)

    def elaborate(self, platform):
        m = Module()

        # TODO without '= m.submodules.pe' warning: UnusedElaboratable 
        pe = m.submodules.pe = PriorityEncoder(width=len(self.ports))
        ports = [port for priority, port in sorted(self.ports.items())]
        
        # if no transacton in-progress..
        with m.If(~self.bus.cyc):
            for i, p in enumerate(ports):
                m.d.sync += pe.i[i].eq(p.cyc) # TODO why not comb?

        # "winning" port idx is in 'pe.o'
        source = Array(ports)[pe.o]

        m.d.comb += [
            self.bus.adr.eq(source.adr),
            self.bus.dat_w.eq(source.dat_w),
            self.bus.sel.eq(source.sel),
            self.bus.cyc.eq(source.cyc),
            self.bus.we.eq(source.we),

            source.dat_r.eq(self.bus.dat_r),
            source.ack.eq(self.bus.ack),
        ]

        return m

    def port(self, priority):
        if priority < 0:
            raise ValueError(f"Negative priority passed! {priority} < 0.")
        if priority in self.ports:
            raise ValueError("Conflicting priority passed to MemoryArbiter.port()")
        port = self.ports[priority] = Record.like(self.bus)
        return port


from common import matcher
from isa import Funct3, InstrType

# match_logic_unit = matcher([
#     (InstrType.ALU, Funct3.OR, 0b0000000),
#     (InstrType.ALU, Funct3.AND, 0b0000000),
#     (InstrType.ALU, Funct3.XOR, 0b0000000),

#     (InstrType.OP_IMM, Funct3.XOR),
#     (InstrType.OP_IMM, Funct3.OR),
#     (InstrType.OP_IMM, Funct3.AND),
# ])

class LoadStoreUnit(Elaboratable):
    def __init__(self, mem_port):
        pass

    def elaborate(self, platform):
        m = Module()

        return m






class LegacyLoadStoreUnit(Elaboratable):
    def __init__(self, depth, mem_init=[0 for _ in range(MEM_WORDS)]):
        self.depth = depth
        self.mem_init = mem_init
        super().__init__()
    def elaborate(self, platform):
        m = Module()

        # self.mem = Memory(width=32, depth=self.depth, init=self.mem_init)
        # read_port = m.submodules.read_port = self.mem.read_port()
        # write_port = m.submodules.write_port = self.mem.write_port()

        # m.d.comb += [
        #     write_port.addr.eq(self.write_addr),
        #     write_port.en.eq(self.write_rdy),
        #     write_port.data.eq(self.write_data),

        #     read_port.addr.eq(self.read_addr),
        #     # read_port.en is Const(1)
        #     self.read_data.eq(read_port.data),

        # ]

        # # dummy all the time valid
        # m.d.comb += [
        #     self.read_vld.eq(True),
        #     self.write_vld.eq(True),
        # ]

        # # dummy 1 cycle read and write, will be more if replace with DDR or any other.
        # m.d.sync += [
        #     self.read_done.eq(self.read_rdy),
        #     self.write_done.eq(self.write_rdy),
        # ]

        return m
