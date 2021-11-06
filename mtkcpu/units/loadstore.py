from typing import Tuple, List, OrderedDict
from nmigen import Cat, Signal, Elaboratable, Module, signed
from nmigen.hdl.rec import Record, DIR_FANOUT, DIR_FANIN
from mtkcpu.utils.common import matcher
from mtkcpu.utils.isa import Funct3, InstrType

MEM_WORDS = 10


wb_bus_layout = [
    ("cyc", 1, DIR_FANIN),
    ("we", 1, DIR_FANIN),
    ("adr", 32, DIR_FANIN),
    ("sel", 4, DIR_FANIN),
    ("dat_w", 32, DIR_FANIN),
    
    ("dat_r", 32, DIR_FANOUT),
    ("ack", 1, DIR_FANOUT),
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
        self.bus_width = 32
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
    def __init__(self) -> None:
        raise NotImplementedError("I need 'bus' param!")

    def __init__(self, bus) -> None:
        self.wb_slave_bus = WishboneSlave(bus, self)
        self.ack = Signal()
        self.dat_r = Signal(32)

    def get_handled_signal(self):
        return self.ack

    def get_dat_r(self):
        return self.dat_r

    def mark_handled_stmt(self):
        return self.get_handled_signal().eq(1)

    def set_dat_r_stmt(self, data):
        return self.get_dat_r().eq(data)
    
    def handle_transaction(self, wb_slv_module):
        raise NotImplementedError()

    def init_owner_module(self) -> Module:
        m = Module()
        m.submodules.wb_slave_bus = self.get_wb_slave_bus() # we don't want each owner to remember about that line
        return m

    def get_wb_slave_bus(self) -> "WishboneSlave":
        return self.wb_slave_bus
     

class GPIO_Wishbone(Elaboratable, BusSlaveOwnerInterface):
    def __init__(self, bus : WishboneBusRecord, signal_map : List[Signal]) -> None:
        BusSlaveOwnerInterface.__init__(self, bus)
        if len(signal_map) > bus.bus_width:
            raise ValueError(f"Error: for now GPIO supports at most 32 signals, passed {len(signal_map)}")
        if len(signal_map) == 0:
            raise ValueError(f"Error: empty GPIO signal map passed! Disable it if not used.")
        self.signal_map = signal_map

    def elaborate(self, platform):
        m = self.init_owner_module()
        return m

    # for now support single 32-bit word.
    def handle_transaction(self, wb_slv_module):
        m = wb_slv_module
        comb = m.d.comb
        sync = m.d.sync

        wb_slave = self.get_wb_slave_bus()
        cyc   = wb_slave.wb_bus.cyc
        write = wb_slave.wb_bus.we
        addr  = wb_slave.wb_bus.adr
        data  = wb_slave.wb_bus.dat_w
        mask  = wb_slave.wb_bus.sel

        gpio_output = Signal(32)

        for i, s in enumerate(self.signal_map):
            if isinstance(s, Signal):
                if s.width != 1:
                    raise ValueError("GPIO: only single bits signals supported!")
                comb += s.eq(gpio_output[i])
            else:
                print(f"GPIO: skipping non-signal value at index {i}..")

        with m.FSM():
            with m.State("GPIO_REQ"):
                with m.If(cyc & (addr == 0x0)):
                    with m.If(write):
                        granularity = 8
                        bus_width = wb_slave.wb_bus.bus_width
                        mask_width = bus_width // granularity
                        assert mask_width == mask.width
                        for i in range(mask_width):
                            # try to emulate 'select'
                            start_incl = i * granularity
                            end_excl = start_incl + granularity
                            with m.If(mask[i]):
                                sync += gpio_output[start_incl:end_excl].eq(data[start_incl:end_excl])
                    with m.Else():
                        sync += self.get_dat_r().eq(gpio_output)
                m.next = "GPIO_RET"
            with m.State("GPIO_RET"):
                comb += self.mark_handled_stmt()
                m.next = "GPIO_REQ"


class EBR_Wishbone(Elaboratable, BusSlaveOwnerInterface):
    def __init__(self, bus : WishboneBusRecord, mem_config : EBRMemConfig) -> None:
        BusSlaveOwnerInterface.__init__(self, bus)
        self.mem_config = mem_config

    def elaborate(self, platform):
        m = self.init_owner_module()
        
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

    def handle_transaction(self, wb_slv_module):
        wb_comb = wb_slv_module.d.comb
        wb_sync = wb_slv_module.d.sync
        wp = self.wp
        rp = self.rp

        wb_slave = self.get_wb_slave_bus()

        cyc   = wb_slave.wb_bus.cyc
        write = wb_slave.wb_bus.we
        addr  = wb_slave.wb_bus.adr
        data  = wb_slave.wb_bus.dat_w
        mask  = wb_slave.wb_bus.sel

        from math import log2
        ws_bytes = self.mem_config.word_size
        ws_bit_shift = Const(log2(ws_bytes))

        real_addr = Signal(32)
        wb_comb += real_addr.eq(addr >> ws_bit_shift)

        # WARNING:
        # that FSM in nested in another one - we have to use Module instance
        # from top-level FSM, otherwise it won't work.
        m = wb_slv_module
        with m.FSM():
            with m.State("EBR_REQ"):
                with m.If(cyc):
                    with m.If(write):
                        wb_comb += [
                            wp.addr.eq(real_addr),
                            wp.data.eq(data),
                            wp.en.eq(mask),
                        ]
                    with m.Else():
                        wb_comb += [
                            rp.addr.eq(real_addr),
                        ]
                m.next = "RET"
            with m.State("RET"):
                wb_sync += self.set_dat_r_stmt(rp.data)
                wb_comb += self.mark_handled_stmt()
                m.next = "EBR_REQ"

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
                    with m.If(self.owner.get_handled_signal()):
                        m.next = "WB_SLV_DONE"
            with m.State("WB_SLV_DONE"):
                dat_r = self.owner.get_dat_r()
                comb += [
                    self.wb_bus.dat_r.eq(dat_r),
                    self.wb_bus.ack.eq(1),
                ]
                m.next = "WB_SLV_TRY_HANDLE"

        return m

class WishboneBusAddressDecoder(Elaboratable):
    def __init__(self, wb_bus : WishboneBusRecord, word_size : int) -> None:
        super().__init__()
        self.ports : OrderedDict[Tuple[int, int], LoadStoreInterface] = {}
        self.bus = wb_bus
        self.word_size = word_size

    def elaborate(self, platform):
        m = Module()
        
        for (start_addr, num_words), slv_bus in self.ports.items():
            max_legal_addr = start_addr + self.word_size * (num_words - 1)
            req_addr = self.bus.adr
            with m.If((req_addr >= start_addr) & (req_addr <= max_legal_addr)):
                m.d.comb += slv_bus.connect(self.bus, exclude=["adr"])
                m.d.comb += slv_bus.adr.eq(req_addr - start_addr)
        return m
    
    def check_addres_scheme(self, addr_scheme : Tuple[int, int]) -> None:
        if addr_scheme[1] <= 0:
            raise ValueError(f"ERROR: num_words={addr_scheme[1]}<=0. Must be positive!")
        
        def overlaps(r1, r2):
            r1, r2 = sorted([r1, r2])
            start_addr1, num_words1 = r1
            start_addr2, _ = r2
            first_allowed = start_addr1 + num_words1 * self.word_size
            return start_addr2 < first_allowed
        
        for r in self.ports.keys():
            if overlaps(addr_scheme, r):
                raise ValueError(f"ERROR: address range {addr_scheme} overlaps with already defined: {r}")
    
    def port(self, addr_scheme : Tuple[int, int]):
        self.check_addres_scheme(addr_scheme)
        bus = self.ports[addr_scheme] = WishboneBusRecord()
        return bus

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

        cfg = self.mem_config
        bridge = m.submodules.bridge = GenericInterfaceToWishboneMasterBridge(generic_bus=self.generic_bus, wb_bus=self.wb_bus)
        decoder = self.decoder = m.submodules.decoder = WishboneBusAddressDecoder(wb_bus=bridge.wb_bus, word_size=cfg.word_size)
        
        mem_decoder_cfg = (cfg.mem_addr, cfg.mem_size_words)
        wb_mem_bus = decoder.port(mem_decoder_cfg)

        gpio_decoder_cfg = (0x8000_0000, 0x1000)
        wb_gpio_bus = decoder.port(gpio_decoder_cfg)

        if platform:
            led_r, led_g = platform.request("led_r"), platform.request("led_g")
        else:
            led_r, led_g = [Signal(name="LED_R"), Signal(name="LED_G")]
        gpio_map = [led_r, led_g]
        
        m.submodules.ebr = self.ebr = EBR_Wishbone(wb_mem_bus, self.mem_config)
        m.submodules.gpio = self.gpio = GPIO_Wishbone(wb_gpio_bus, signal_map=gpio_map)
        
        pe = m.submodules.pe = self.pe = PriorityEncoder(width=len(self.ports))
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


class GenericInterfaceToWishboneMasterBridge(Elaboratable):
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
