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
    ("we",     1, DIR_FANOUT),
]

# implements 'ready/valid' via '~busy' and 'en' signals. 
class LoadStoreInterface():

    def __init__(self):
        # Input signals.
        self.en = Signal(name="EN")
        self.store = Signal()
        
        self.addr = Signal(32, name="ADDR")
        self.mask = Signal(4)

        self.write_data = Signal(32)

        # Output signals.
        self.busy = Signal(name="BUSY")
        self.read_data = Signal(32)
        
        self.ack = Signal(name="ACK")


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

match_load = matcher([
    (InstrType.LOAD, Funct3.B),
    (InstrType.LOAD, Funct3.BU),
    (InstrType.LOAD, Funct3.H),
    (InstrType.LOAD, Funct3.HU),
])

match_store = matcher([
    (InstrType.STORE, Funct3.B),
    (InstrType.STORE, Funct3.BU),
    (InstrType.STORE, Funct3.H),
    (InstrType.STORE, Funct3.HU),
])

match_loadstore_unit = lambda op, f3, f7: match_load(op, f3, f7) | match_store(op, f3, f7)

class Selector(Elaboratable):
    def __init__(self):
        self.mask = Signal(4)
        self.funct3 = Signal(Funct3)
        self.store = Signal()

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        u = Signal() # unsigned
        comb += u.eq((self.funct3 == Funct3.HU) | (self.funct3 == Funct3.BU) )
        
        with m.Switch(self.funct3):
            with m.Case(Funct3.W):
                comb += self.mask.eq(0b1111)
            with m.Case(Funct3.H):
                comb += self.mask.eq(0b0011)
            with m.Case(Funct3.B):
                comb += self.mask.eq(0b0001)
            with m.Case(Funct3.HU):
                comb += self.mask.eq(0b0011)
            with m.Case(Funct3.BU):
                comb += self.mask.eq(0b0001)
        with m.If(self.store & ~u):
            comb += self.mask.eq(0b1111)

        return m

def prefix_all_signals(obj, prefix):
    for attr_name in dir(obj):
        sig = getattr(obj, attr_name)
        if type(sig) == Signal:
            sig.name = prefix + sig.name


class LoadStoreUnit(Elaboratable, LoadStoreInterface):
    def __init__(self, mem_port):
        super().__init__()
        self.mem_port = mem_port

    def elaborate(self, platform):
        m = Module()

        comb = m.d.comb
        sync = m.d.sync

        comb += [
            self.busy.eq(self.mem_port.cyc),
        ]

        sync += [
            self.mem_port.adr.eq(self.addr),
            self.mem_port.dat_w.eq(self.write_data),
            self.mem_port.sel.eq(self.mask),
            self.mem_port.we.eq(self.store),

            self.read_data.eq(self.mem_port.dat_r),
        ]

        # suppress ack signals (asserted during one cycle).
        with m.If(self.ack):
            sync += [
                self.ack.eq(0)
            ]

        with m.If(self.mem_port.cyc):
            with m.If(self.mem_port.ack):
                sync += [
                    self.mem_port.cyc.eq(0),
                    self.ack.eq(1)
                ]               
        with m.Else():
            sync += [
                self.mem_port.cyc.eq(self.en),
            ]

        return m

class MemoryUnit(Elaboratable):
    def __init__(self, mem_port):

        self.loadstore = LoadStoreUnit(mem_port)
        
        # Input signals.
        self.funct3 = Signal(Funct3)
        self.src1 = Signal(32)

        # 'src2' is used only for 'store' instructions.
        self.src2 = Signal(32)
        self.offset = Signal(signed(12))

        self.res = Signal(32)
        self.en = Signal() # TODO do 'ready/valid' interface

        # Output signals.
        self.ack = Signal()
        

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d.sync
        loadstore = m.submodules.loadstore = self.loadstore

        store = Signal()
        addr = Signal(32)
        
        comb += [
            store.eq(self.funct3 == InstrType.STORE),
            addr.eq(self.offset + self.src1),
        ]

        sel = m.submodules.sel = Selector()

        # sel.mask will be calculated.
        comb += [
            sel.funct3.eq(self.funct3),
            sel.store.eq(store),
        ]

        word = Signal(32)
        half_word = Signal(16)
        byte = Signal(8)

        comb += [
            word.eq(self.src2),
            half_word.eq(self.src2[0:16]),
            byte.eq(self.src2[0:8]),
        ]

        write_data = Signal(32)
        signed_write_data = Signal(signed(32))

        with m.If(store):
            with m.Switch(self.funct3):
                with m.Case(Funct3.W):
                    comb += write_data.eq(word),
                with m.Case(Funct3.H):
                    comb += [
                        signed_write_data.eq(half_word),
                        write_data.eq(signed_write_data),    
                    ]
                with m.Case(Funct3.B):
                    comb += [
                        signed_write_data.eq(byte),
                        write_data.eq(signed_write_data),    
                    ]
                with m.Case(Funct3.HU):
                    comb += write_data.eq(half_word),
                with m.Case(Funct3.BU):
                    comb += write_data.eq(byte),
        
        with m.FSM() as fsm:
            with m.State("IDLE"):
                with m.If(self.en):
                    comb += [
                        loadstore.en.eq(1),
                        loadstore.store.eq(store),
                        loadstore.addr.eq(addr),
                        loadstore.mask.eq(sel.mask),
                        loadstore.write_data.eq(write_data), 
                    ]
                    m.next = "WAIT"
                with m.Else():
                    m.next = "IDLE"
            with m.State("WAIT"):
                with m.If(loadstore.ack):
                    comb += [
                        self.ack.eq(1),
                        self.res.eq(loadstore.read_data),
                    ]
                    m.next = "IDLE"

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
