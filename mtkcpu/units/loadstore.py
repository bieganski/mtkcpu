from argparse import ArgumentError
from enum import IntEnum, unique
from typing import Tuple, OrderedDict
from amaranth import Cat, Signal, Const, Elaboratable, Module, signed, Mux
from amaranth.hdl.rec import Record, DIR_FANOUT, DIR_FANIN
from mtkcpu.cpu.priv_isa import PrivModeBits, pte_layout, virt_addr_layout
from mtkcpu.units.csr import CsrUnit
from mtkcpu.units.exception import ExceptionUnit
from mtkcpu.utils.common import matcher, EBRMemConfig
from mtkcpu.cpu.isa import Funct3, InstrType

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


class WishboneSlave(Elaboratable):
    def __init__(self, wb_bus : WishboneBusRecord, owner: "BusSlaveOwnerInterface") -> None:
        self.wb_bus = wb_bus
        self.owner = owner
    
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


class BusSlaveOwnerInterface:
    def __init__(self) -> None:
        self.wb_slave_bus = None
        self.ack = Signal()
        self.dat_r = Signal(32)
        self._wb_slave_bus = None

    def init_bus_slave(self, bus):
        self._wb_slave_bus = WishboneSlave(bus, self)

    def get_handled_signal(self):
        return self.ack

    def get_dat_r(self):
        return self.dat_r

    def mark_handled_stmt(self):
        return self.get_handled_signal().eq(1)

    def set_dat_r_stmt(self, data):
        return self.get_dat_r().eq(data)

    def handle_transaction(self, wb_slv_module) -> None:
        raise NotImplementedError("BusSlaveOwnerInterface must implement 'handle_transaction' method!")

    # TODO move it
    def init_owner_module(self) -> Module:
        m = Module()
        m.submodules.wb_slave_bus = self.get_wb_slave_bus() # we don't want each owner to remember about that line
        return m

    def get_wb_slave_bus(self) -> WishboneSlave:
        res = self._wb_slave_bus
        if not res:
            raise ValueError("ERROR: init_bus_slave method must be called before trying to access bus!")
        return res
    
from mtkcpu.units.memory_interface import MMIOAddressSpace

class WishboneBusAddressDecoder(Elaboratable):
    def __init__(self, wb_bus : WishboneBusRecord, word_size : int) -> None:
        super().__init__()
        self.ports : OrderedDict[MMIOAddressSpace, LoadStoreInterface] = {}
        self.bus = wb_bus
        self.word_size = word_size

    def elaborate(self, platform):
        m = Module()
        
        for addr_scheme, slv_bus in self.ports.items():
            num_words = addr_scheme.num_words
            start_addr = addr_scheme.first_valid_addr_incl
            max_legal_addr = start_addr + self.word_size * (num_words - 1)
            req_addr = self.bus.adr
            with m.If((req_addr >= start_addr) & (req_addr <= max_legal_addr)):
                m.d.comb += slv_bus.connect(self.bus, exclude=["adr"])
                m.d.comb += slv_bus.adr.eq(req_addr - start_addr)
        return m
    
    def check_addres_scheme(self, addr_scheme : MMIOAddressSpace) -> None:
        if addr_scheme.num_words == 0:
            print(f"WARNING: num_words={addr_scheme[1]}==0. Efectively your design will lack of EBR memory!")
        
        def overlaps(r1, r2):
            r1, r2 = sorted([r1, r2], key=lambda x: x.first_valid_addr_incl)
            start_addr1, num_words1 = r1.first_valid_addr_incl, r1.num_words
            start_addr2 = r2.first_valid_addr_incl
            first_allowed = start_addr1 + num_words1 * self.word_size
            return start_addr2 < first_allowed
        
        for r in self.ports.keys():
            if overlaps(addr_scheme, r):
                raise ValueError(f"ERROR: address range {addr_scheme} overlaps with already defined: {r}")
    
    def port(self, addr_scheme : MMIOAddressSpace):
        self.check_addres_scheme(addr_scheme)
        bus = self.ports[addr_scheme] = WishboneBusRecord()
        return bus

from typing import List, Tuple
from amaranth.build import Platform

from mtkcpu.units.mmio.ebr import EBR_Wishbone
from mtkcpu.units.mmio.gpio import GPIO_Wishbone
from mtkcpu.units.memory_interface import MMIOAddressSpace, AddressManager

class MemoryArbiter(Elaboratable, AddressManager):
    def __init__(self):
        raise ArgumentError("lack of 'mem_config' param!")

    def __init__(self, mem_config: EBRMemConfig, with_addr_translation: bool, csr_unit: CsrUnit, exception_unit : ExceptionUnit):
        self.ports = {}
        self.word_size = 4
        self.generic_bus = LoadStoreInterface(name="generic_bus")
        self.wb_bus = WishboneBusRecord()
        self.mem_config = mem_config
        self.with_addr_translation = with_addr_translation
        self.csr_unit = csr_unit
        self.exception_unit = exception_unit
        self.__gen_mmio_devices_config_once()

    def __gen_mmio_devices_config_once(self) -> None:
        assert getattr(self, "mmio_cfg", None) is None

        def gpio_gen(platform : Platform):
            if platform:
                led_r, led_g = platform.request("led_r"), platform.request("led_g")
            else:
                led_r, led_g = [Signal(name="LED_R"), Signal(name="LED_G")]
            self.led_r, self.led_g = led_r, led_g # TODO this is obfuscated, but we need those signals for simulation testbench
            return [led_r, led_g]

        from mtkcpu.units.mmio.uart import UartTX
        from amaranth.hdl.rec import Layout
        from amaranth import Const

        def uart_gen_serial_record(platform : Platform, m : Module):
            if platform:
                serial = platform.request("uart")
                debug = platform.request("debug")
                m.d.comb += [
                    debug.eq(Cat(
                        serial.tx,
                        Const(0, 1), # GND
                    ))
                ]
            else:
                serial = Record(Layout([("tx", 1)]), name="UART_SERIAL")
            self.serial = serial # TODO this is obfuscated, but we need those signals for simulation testbench
            
            return serial

        self.mmio_cfg = [
            (
                UartTX(serial_record_gen=uart_gen_serial_record, clk_freq=12_000_000, baud_rate=115200),
                MMIOAddressSpace(
                    ws=self.word_size,
                    basename="uart",
                    first_valid_addr_incl=0x7000_0000,
                    last_valid_addr_excl=0x7000_1000,
                )
            ),
            (
                EBR_Wishbone(self.mem_config),
                MMIOAddressSpace(
                    ws=self.word_size,
                    basename="ebr",
                    first_valid_addr_incl=self.mem_config.mem_addr,
                    last_valid_addr_excl=self.mem_config.last_valid_addr_excl,
                )
            ),
            (
                GPIO_Wishbone(signal_map_gen=gpio_gen),
                MMIOAddressSpace(
                    ws=self.word_size,
                    basename="gpio",
                    first_valid_addr_incl=0x9000_0000,
                    last_valid_addr_excl=0x9000_1000,
                )
            )
        ]

    def get_mmio_devices_config(self) -> List[Tuple[BusSlaveOwnerInterface, MMIOAddressSpace]]:
        return self.mmio_cfg

    def elaborate(self, platform):
        m = Module()
        sync = m.d.sync
        comb = m.d.comb

        cfg = self.mem_config
        bridge = m.submodules.bridge = GenericInterfaceToWishboneMasterBridge(generic_bus=self.generic_bus, wb_bus=self.wb_bus)
        self.decoder = m.submodules.decoder = WishboneBusAddressDecoder(wb_bus=bridge.wb_bus, word_size=cfg.word_size)
        self.initialize_mmio_devices(self.decoder, m)
        pe = m.submodules.pe = self.pe = PriorityEncoder(width=len(self.ports))
        sorted_ports = [port for priority, port in sorted(self.ports.items())]
        
        # force 'elaborate' invocation for all mmio modules.
        for mmio_module, addr_space in self.mmio_cfg:
            setattr(m.submodules, addr_space.basename, mmio_module)
        
        addr_translation_en = Signal()
        bus_free_to_latch = Signal(reset=1)

        if self.with_addr_translation:
            m.d.comb += addr_translation_en.eq(self.csr_unit.satp.mode & (self.exception_unit.current_priv_mode == PrivModeBits.USER))
        else:
            m.d.comb += addr_translation_en.eq(False)

        with m.If(~addr_translation_en):
            # when translation enabled, 'bus_free_to_latch' is low during page-walk.
            # with no translation it's simpler - just look at the main bus.
            m.d.comb += bus_free_to_latch.eq(~self.generic_bus.busy)
        
        with m.If(bus_free_to_latch):
            # no transaction in-progress
            for i, p in enumerate(sorted_ports):
                m.d.sync += pe.i[i].eq(p.en)

        
        virtual_req_bus_latch = LoadStoreInterface()
        phys_addr = Signal(32)
        
        # translation-unit controller signals. 
        start_translation = Signal()
        translation_ack = Signal()
        gb = self.generic_bus

        with m.If(~pe.none):
            # transaction request occured
            for i, priority in enumerate(sorted_ports):
                with m.If(pe.o == i):
                    bus_owner_port = sorted_ports[i]
                    with m.If(~addr_translation_en):
                        # simple case, no need to calculate physical address
                        comb += gb.connect(bus_owner_port)
                    with m.Else():
                        # page-walk performs multiple memory operations - will reconnect 'generic_bus' multiple times
                        with m.FSM():
                            first = Signal() # TODO get rid of that
                            with m.State("TRANSLATE"):
                                comb += [
                                    start_translation.eq(1),
                                    bus_free_to_latch.eq(0),
                                ]
                                sync += virtual_req_bus_latch.connect(bus_owner_port, exclude=[name for name, _, dir in generic_bus_layout if dir == DIR_FANOUT])
                                with m.If(translation_ack): # wait for 'phys_addr' to be set by page-walk algorithm.
                                    m.next = "REQ"
                                sync += first.eq(1)
                            with m.State("REQ"):
                                comb += gb.connect(bus_owner_port, exclude=["addr"])
                                comb += gb.addr.eq(phys_addr) # found by page-walk
                                with m.If(first):
                                    sync += first.eq(0)
                                with m.Else():
                                    # without 'first' signal '~gb.busy' would be high at the very beginning 
                                    with m.If(~gb.busy):
                                        comb += bus_free_to_latch.eq(1)
                                        m.next = "TRANSLATE"
        
        req_is_write = Signal()
        pte = Record(pte_layout)
        vaddr = Record(virt_addr_layout)
        comb += [
            req_is_write.eq(virtual_req_bus_latch.store),
            vaddr.eq(virtual_req_bus_latch.addr),
        ]

        @unique
        class Issue(IntEnum):
            OK = 0
            PAGE_INVALID = 1
            WRITABLE_NOT_READABLE = 2
            LACK_PERMISSIONS = 3
            FIRST_ACCESS_OR_MAKE_DIRTY = 4
            MISALIGNED_SUPERPAGE = 5
            LEAF_IS_NO_LEAF = 6

        self.error_code = Signal(Issue)
        def error(code: Issue):
            m.d.sync += self.error_code.eq(code)

        # Code below implements algorithm 4.3.2 in Risc-V Privileged specification, v1.10
        sv32_i = Signal(reset=1)
        root_ppn = Signal(22)
        
        with m.FSM():
            with m.State("IDLE"):
                with m.If(start_translation):
                    sync += sv32_i.eq(1)
                    sync += root_ppn.eq(self.csr_unit.satp.ppn)
                    m.next = "TRANSLATE"
            with m.State("TRANSLATE"):
                vpn = Signal(10)
                comb += vpn.eq(Mux(
                    sv32_i,
                    vaddr.vpn1,
                    vaddr.vpn0,
                ))
                comb += [
                    gb.en.eq(1),
                    gb.addr.eq(Cat(Const(0, 2), vpn, root_ppn)),
                    gb.store.eq(0),
                    gb.mask.eq(0b1111), # TODO use -1
                ]
                with m.If(gb.ack):
                    sync += pte.eq(gb.read_data)
                    m.next = "PROCESS_PTE"
            with m.State("PROCESS_PTE"):
                with m.If(~pte.v):
                    error(Issue.PAGE_INVALID)
                with m.If(pte.w & ~pte.r):
                    error(Issue.WRITABLE_NOT_READABLE)

                is_leaf = lambda pte: ~(pte.r | pte.x)
                with m.If(is_leaf(pte)):
                    with m.If(~pte.u & (self.exception_unit.current_priv_mode == PrivModeBits.USER)):
                        error(Issue.LACK_PERMISSIONS)
                    with m.If(~pte.a | (req_is_write & ~pte.d)):
                        error(Issue.FIRST_ACCESS_OR_MAKE_DIRTY)
                    with m.If(sv32_i.bool() & pte.ppn0.bool()):
                        error(Issue.MISALIGNED_SUPERPAGE)
                    phys_addr = Signal(32)
                    # phys_addr could be 34 bits long, but our interconnect is 32-bit long.
                    # below statement cuts lowest two bits of r-value.
                    sync += phys_addr.eq(Cat(vaddr.page_offset, pte.ppn0, pte.ppn1))
                with m.Else(): # not a leaf
                    with m.If(sv32_i == 0):
                        error(Issue.LEAF_IS_NO_LEAF)
                    sync += root_ppn.eq(Cat(pte.ppn0, pte.ppn1)) # pte a is pointer to the next level
                m.next = "NEXT"
            with m.State("NEXT"):
                # Note that we cannot check 'sv32_i == 0', becuase superpages can be present.
                with m.If(is_leaf(pte)):
                    sync += sv32_i.eq(1)
                    comb += translation_ack.eq(1) # notify that 'phys_addr' signal is set
                    m.next = "IDLE"
                with m.Else():
                    sync += sv32_i.eq(0)
                    m.next = "TRANSLATE"
        return m

    def port(self, priority):
        if priority < 0:
            raise ValueError(f"Negative priority passed! {priority} < 0.")
        if priority in self.ports:
            raise ValueError(
                f"Conflicting priority passed to MemoryArbiter.port(): {priority}"
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

        addr_lsb = Signal(2)
        m.d.comb += addr_lsb.eq(addr[:2]) # XXX

        # allow naturally aligned addresses
        # TODO trap on wrong address
        with m.If(store):
            data = self.src2
            comb += [
                word.eq(data),
                half_word.eq(data.word_select(addr_lsb[1], 16)),
                byte.eq(data.word_select(addr_lsb, 8)),
            ]
        with m.Else():
            data = loadstore.read_data
            comb += [
                word.eq(data),
                half_word.eq(data.word_select(addr_lsb[1], 16)),
                byte.eq(data.word_select(addr_lsb, 8))
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
