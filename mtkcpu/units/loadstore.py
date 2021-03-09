from nmigen import *
from enum import Enum

MEM_WORDS = 10

class LoadStoreInterface():
    def __init__(self):
        # input signals.
        self.write_rdy = Signal()
        self.read_rdy = Signal()
        self.read_addr = Signal(32)
        self.write_addr = Signal(32)
        self.write_data = Signal(32)

        # output signals.
        self.read_vld = Signal()
        self.write_vld = Signal()
        self.read_data = Signal(32)
        
        self.read_done = Signal()
        self.write_done = Signal()


class LoadStoreUnit(LoadStoreInterface, Elaboratable):
    def __init__(self, depth, mem_init=[0 for _ in range(MEM_WORDS)]):
        self.depth = depth
        self.mem_init = mem_init
        super().__init__()
    def elaborate(self, platform):
        m = Module()

        self.mem = Memory(width=32, depth=self.depth, init=self.mem_init)
        read_port = m.submodules.read_port = self.mem.read_port()
        write_port = m.submodules.write_port = self.mem.write_port()

        m.d.comb += [
            write_port.addr.eq(self.write_addr),
            write_port.en.eq(self.write_rdy),
            write_port.data.eq(self.write_data),

            read_port.addr.eq(self.read_addr),
            # read_port.en is Const(1)
            self.read_data.eq(read_port.data),

        ]

        # dummy all the time valid
        m.d.comb += [
            self.read_vld.eq(True),
            self.write_vld.eq(True),
        ]

        # dummy 1 cycle read and write, will be more if replace with DDR or any other.
        m.d.sync += [
            self.read_done.eq(self.read_rdy),
            self.write_done.eq(self.write_rdy),
        ]

        return m
