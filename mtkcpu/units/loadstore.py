from __future__ import generator_stop
from os import name
from typing import overload
from nmigen import Cat, Signal, Elaboratable, Module, signed, Array
from nmigen.hdl import rec
from nmigen.hdl.rec import Record, DIR_FANOUT, DIR_FANIN
from mtkcpu.utils.common import START_ADDR, matcher
from mtkcpu.utils.isa import Funct3, InstrType

MEM_WORDS = 10


wb_bus_layout = [
    ("adr", 32, DIR_FANOUT),  # addresses aligned to 4
    ("dat_w", 32, DIR_FANOUT),
    ("dat_r", 32, DIR_FANIN),
    ("sel", 4, DIR_FANOUT),
    ("cyc", 1, DIR_FANOUT),
    ("ack", 1, DIR_FANIN),
    ("we", 1, DIR_FANOUT),
]

generic_bus_layout = [
    ("en", 1, DIR_FANIN),
    ("store", 1, DIR_FANIN),
    ("addr", 32, DIR_FANIN),
    ("mask", 4, DIR_FANIN),
    ("write_data", 32, DIR_FANIN),

    ("busy", 1, DIR_FANOUT),
    ("read_data", 32, DIR_FANOUT),
    ("ack", 1, DIR_FANOUT),
]

class WishboneBusRecord(Record):
    def __init__(self, *args, **kwargs):
        super().__init__(self.__layout, *args, **kwargs)

    @property
    def __layout(self):
        return wb_bus_layout


class LoadStoreInterface(Record):
    def __init__(self, *args, **kwargs):
        super().__init__(self.__layout, *args, **kwargs)

    @property
    def __layout(self):
        return generic_bus_layout


class PriorityEncoder(Elaboratable):
    def __init__(self, width):
        self.width = width
        self.i = Signal(self.width)
        self.o = Signal(range(self.width), name="PE_o")

        self.none = Signal()

    def elaborate(self, platform):
        m = Module()

        for k in reversed(range(self.width)):
            with m.If(self.i[k]):
                m.d.comb += self.o.eq(k)
        m.d.comb += self.none.eq(self.i == 0)  # no requests

        return m

from nmigen import *
from mtkcpu.utils.common import EBRMemConfig

class BusSlaveOwnerInterface():
    def __init__(self):
        raise ValueError("__init__ call needs reference for owner instance's elaboratable module!")

    def __init__(self, module: Module) -> None:
        self.m = module
        self.ack = Signal(reset=0)
        self.dat_r = Signal(32, reset=0xdeadbeef)

    def get_handled_signal(self):
        return self.ack

    def get_dat_r(self):
        return self.dat_r

    def mark_handled_instant(self):
        self.m.d.comb += self.ack.eq(1)

    def set_dat_r_sync(self, data):
        self.m.d.sync += self.dat_r.eq(data)
    
    @overload
    def handle_transaction(self):
        raise NotImplementedError()


class EBR_Wishbone(Elaboratable, BusSlaveOwnerInterface):
    def __init__(self, bus : WishboneBusRecord, mem_config : EBRMemConfig) -> None:
        self.wb_slave = WishboneSlave(bus, self)
        self.mem_config = mem_config

    def elaborate(self, platform):
        m = Module()
        BusSlaveOwnerInterface.__init__(self, module=m)

        # XXX That's bad that each owner needs to remember about that line.
        m.submodules.wb_slave = self.wb_slave
        
        cfg = self.mem_config
        assert cfg.word_size == 4

        mem = self.mem = Memory(
            depth=cfg.mem_size_words, 
            width=cfg.word_size * 8,
            init=cfg.mem_content_words,
            simulate=cfg.simulate,
            # https://www.mimuw.edu.pl/~mwk/pul/03_ram/index.html
        )
        m.submodules.wp = self.wp = mem.write_port(granularity=8)
        m.submodules.rp = self.rp = mem.read_port()

        self.leds = Signal(32, attrs={"KEEP": True, "keep":True})
            
        return m

    def handle_transaction(self, m):
        comb = m.d.comb
        sync = m.d.sync
        wp = self.wp
        rp = self.rp

        cyc   = self.wb_slave.wb_bus.cyc
        write = self.wb_slave.wb_bus.we
        addr  = self.wb_slave.wb_bus.adr
        data  = self.wb_slave.wb_bus.dat_w
        mask  = self.wb_slave.wb_bus.sel

        self.ACK = Signal(name="ACEK")

        from math import log2
        ws_bytes = self.mem_config.word_size
        ws_bit_shift = Const(log2(ws_bytes))

        real_addr = Signal(32)
        comb += real_addr.eq((addr - self.mem_config.mem_addr) >> ws_bit_shift)

        # WARNING:
        # that FSM in nested in another one - we have to use Module instance
        # from top-level FSM, otherwise it won't work.
        with m.FSM():
            with m.State("EBR_REQ"):
                with m.If(cyc):
                    with m.If(write):
                        comb += [
                            # wp.en.eq(1),
                            wp.addr.eq(real_addr),
                            wp.data.eq(data),
                            wp.en.eq(mask),
                        ]
                    with m.Else():
                        comb += [
                            rp.addr.eq(real_addr),
                            # TODO mask nie wspierane dla read_port
                        ]
                m.next = "RET"
            with m.State("RET"):
                sync += self.dat_r.eq(rp.data)
                comb += self.ACK.eq(1)
                m.next = "EBR_REQ"
                # self.mark_handled_instant()

class WishboneSlave(Elaboratable):
    def __init__(self, wb_bus : WishboneBusRecord, owner: BusSlaveOwnerInterface) -> None:
        self.wb_bus = wb_bus
        self.owner = owner
        assert isinstance(owner, BusSlaveOwnerInterface)
    
    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d.sync

        with m.FSM():
            with m.State("WB_SLV_TRY_HANDLE"):
                comb += self.wb_bus.ack.eq(0)
                with m.If(self.wb_bus.cyc):
                    self.owner.handle_transaction(m)
                    with m.If(self.owner.ACK):
                        m.next = "WB_SLV_DONE"
            with m.State("WB_SLV_DONE"):
                dat_r = self.owner.dat_r
                comb += [
                    self.wb_bus.dat_r.eq(dat_r),
                    self.wb_bus.ack.eq(1),
                ]
                m.next = "WB_SLV_TRY_HANDLE"

        return m

class MemoryArbiter(Elaboratable):
    def __init__(self, mem_config: EBRMemConfig):
        self.ports = {}
        self.generic_bus = LoadStoreInterface(name="generic_bus")
        self.wb_bus = WishboneBusRecord()
        self.mem_config = mem_config

    def elaborate(self, platform):
        m = Module()
        sync = m.d.sync
        comb = m.d.comb
        # TODO lack of address decoder
        print("Initializing EBR memory..")
        m.submodules.bridge = InterfaceToWishboneMasterBridge(wb_bus=self.wb_bus, generic_bus=self.generic_bus)
        m.submodules.ebr = self.ebr = EBR_Wishbone(m.submodules.bridge.wb_bus, self.mem_config)
        pe = m.submodules.pe = self.pe = PriorityEncoder(width=len(self.ports))

        none_latch = Signal()
        sync += none_latch.eq(pe.none)

        sorted_ports = [port for priority, port in sorted(self.ports.items())]

        with m.If(~self.generic_bus.busy):
            # no transaction in-progress
            for i, p in enumerate(sorted_ports):
                m.d.sync += pe.i[i].eq(p.en)

        # TODO not used as Array doesn't support 'connect' method
        # "winning" port idx is in 'pe.o'
        # source = Array(sorted_ports)[pe.o]
        with m.If(~pe.none):
            for i, priority in enumerate(sorted_ports):
                with m.If(pe.o == i):
                    m.d.comb += self.generic_bus.connect(sorted_ports[i])

        return m

    def port(self, priority):
        if priority < 0:
            raise ValueError(f"Negative priority passed! {priority} < 0.")
        if priority in self.ports:
            raise ValueError(
                "Conflicting priority passed to MemoryArbiter.port()"
            )
        port = self.ports[priority] = LoadStoreInterface()
        return port


match_load = matcher(
    [
        (InstrType.LOAD, Funct3.W),
        (InstrType.LOAD, Funct3.B),
        (InstrType.LOAD, Funct3.BU),
        (InstrType.LOAD, Funct3.H),
        (InstrType.LOAD, Funct3.HU),
    ]
)

match_store = matcher(
    [
        (InstrType.STORE, Funct3.W),
        (InstrType.STORE, Funct3.B),
        # (InstrType.STORE, Funct3.BU), # it doesn't exist
        (InstrType.STORE, Funct3.H),
        # (InstrType.STORE, Funct3.HU), # it doesn't exist
    ]
)


def match_loadstore_unit(op, f3, f7):
    return match_load(op, f3, f7) | match_store(
        op, f3, f7
    )


class Selector(Elaboratable):
    def __init__(self):
        self.mask = Signal(4, name="SEL_mask")
        self.funct3 = Signal(Funct3)
        self.store = Signal()

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb

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

        return m


def prefix_all_signals(obj, prefix):
    for attr_name in dir(obj):
        sig = getattr(obj, attr_name)
        if type(sig) == Signal:
            sig.name = prefix + sig.name


class InterfaceToWishboneMasterBridge(Elaboratable):
    def __init__(self, wb_bus : WishboneBusRecord, generic_bus : LoadStoreInterface):
        super().__init__()
        self.wb_bus = wb_bus
        self.generic_bus = generic_bus

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d.sync
        gb = self.generic_bus
        wb = self.wb_bus

        # XXX for now we don't use strobe signal (cyc only)
        with m.FSM():
            with m.State("IDLE"):
                sync += [
                    wb.adr.eq(gb.addr),
                    wb.dat_w.eq(gb.write_data),
                    wb.sel.eq(gb.mask),
                    wb.we.eq(gb.store),
                ]
                with m.If(gb.en):
                    sync += [
                        wb.cyc.eq(1),
                        gb.busy.eq(1),
                    ]
                    m.next = "WAIT_MEM"
            with m.State("WAIT_MEM"):
                with m.If(wb.ack):
                    sync += [
                        wb.cyc.eq(0),
                        gb.ack.eq(1),
                        gb.read_data.eq(wb.dat_r),
                    ]
                    m.next = "PARK"
            with m.State("PARK"):
                sync += [
                    gb.busy.eq(0),
                    gb.ack.eq(0) # don't assert it for too long
                ]
                m.next = "IDLE"
        return m


class MemoryUnit(Elaboratable):
    def __init__(self, mem_port : LoadStoreInterface):

        self.loadstore = mem_port

        # Input signals.
        self.store = Signal()  # assume 'load' if deasserted.
        self.funct3 = Signal(Funct3)
        self.src1 = Signal(32, name="LD_ST_src1")

        # 'src2' is used only for 'store' instructions.
        self.src2 = Signal(32, name="LD_ST_src2")
        self.offset = Signal(signed(12), name="LD_ST_offset")

        self.res = Signal(signed(32), name="LD_ST_res")
        self.en = Signal(name="LD_ST_en")  # TODO implement 'ready/valid' interface

        # Output signals.
        self.ack = Signal(name="LD_ST_ack")

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d.sync
        loadstore = self.loadstore

        store = self.store
        addr = Signal(32)

        comb += [
            addr.eq(self.offset + self.src1),
        ]

        sel = m.submodules.sel = Selector()

        # sel.mask will be calculated.
        comb += [
            sel.funct3.eq(self.funct3),
            sel.store.eq(store),
        ]

        word = Signal(signed(32))
        half_word = Signal(signed(16))
        byte = Signal(8)

        write_data = Signal(32)
        signed_write_data = Signal(signed(32))

        load_res = Signal(signed(32))

        with m.If(store):
            comb += [
                word.eq(self.src2),
                half_word.eq(self.src2[0:16]),
                byte.eq(self.src2[0:8]),
            ]
        with m.Else():
            comb += [
                word.eq(loadstore.read_data),
                half_word.eq(loadstore.read_data[0:16]),
                byte.eq(loadstore.read_data[0:8]),
            ]

        with m.If(~store):
            with m.Switch(self.funct3):
                with m.Case(Funct3.W):
                    comb += load_res.eq(word)
                with m.Case(Funct3.H):
                    comb += load_res.eq(half_word)
                with m.Case(Funct3.B):
                    comb += load_res.eq(byte)
                with m.Case(Funct3.HU):
                    comb += load_res.eq(Cat(half_word, 0))
                with m.Case(Funct3.BU):
                    comb += load_res.eq(Cat(byte, 0))

        with m.If(store):
            with m.Switch(self.funct3):
                with m.Case(Funct3.W):
                    comb += (write_data.eq(word),)
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
                    comb += (write_data.eq(half_word),)
                with m.Case(Funct3.BU):
                    comb += (write_data.eq(byte),)

        with m.FSM():
            with m.State("IDLE"):
                with m.If(self.en):
                    sync += [
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
                        self.res.eq(load_res),
                    ]
                    sync += loadstore.en.eq(0)
                    m.next = "IDLE"

        return m
