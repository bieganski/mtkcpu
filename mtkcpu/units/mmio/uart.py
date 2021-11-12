# This example is based on Whitequark's lab notebook
# https://lab.whitequark.org/notes/2016-10-18/implementing-an-uart-in-verilog-and-migen/

from ctypes import ArgumentError
from nmigen import *
from nmigen.build import *
from nmigen_boards.icebreaker import *


def _divisor(freq_in, freq_out, max_ppm=None):
    divisor = freq_in // freq_out
    if divisor <= 0:
        raise ArgumentError("Output frequency is too high.")

    ppm = 100000 * ((freq_in / divisor) - freq_out) / freq_out
    if max_ppm is not None and ppm > max_ppm:
        raise ArgumentError("Output frequency deviation is too high.")

    return divisor

from mtkcpu.units.loadstore import BusSlaveOwnerInterface, LoadStoreInterface
from mtkcpu.units.mmio.bspgen import BspGeneratable, MMIOPeriphConfig, MMIORegister

class UartTX(Elaboratable, BusSlaveOwnerInterface, BspGeneratable):
    def __init__(self, serial, clk_freq, baud_rate):
        self.rx_data = Signal(8)
        self.rx_ready = Signal()
        self.rx_ack = Signal()
        self.rx_error = Signal()
        self.rx_strobe = Signal()
        self.rx_bitno = None
        self.rx_fsm = None

        self.tx_data = Signal(8, reset=ord('x'))
        self.tx_ready = Signal()
        self.tx_ack = Signal()
        self.tx_strobe = Signal()
        self.tx_bitno = None
        self.tx_latch = None
        self.tx_fsm = None

        self.serial = serial

        self.divisor = _divisor(
            freq_in=clk_freq, freq_out=baud_rate, max_ppm=50000)

    def get_periph_config(self) -> MMIOPeriphConfig:
        return MMIOPeriphConfig(
            basename='uart',
            regions=[],
            first_valid_addr=0, # XXX FIXME
            last_valid_addr=0,
            registers=[
                MMIORegister(
                    name="tx_busy",
                    addr=0x0,
                    description="Read only - non-zero value means UART is busy and write to tx_data will have no effect. "
                    "Otherwise write to tx_data will trigger byte send.",
                    bits=[],
                ),
                MMIORegister(
                    "tx_data",
                    addr=0x8,
                    description="Data byte to be sent. Width of this register is 8 bits."
                ),
            ]
        )
    
    def handle_transaction(self, wb_slv_module):
        m = wb_slv_module
        sync = m.d.sync
        comb = m.d.comb

        bus = self.get_wb_slave_bus()

        with m.FSM():
            with m.State("IDLE"):
                with m.If(bus.cyc):
                    with m.Switch(bus.adr):
                        with m.Case(0x0):
                            with m.If(bus.we == 0):
                                # read only.
                                sync += [
                                    self.get_dat_r().eq(self.busy_mmio),
                                ]
                        with m.Case(0x8):
                            with m.If(bus.we[0] == 1):
                                # write only, of 8-bits width.
                                comb += [
                                    self.tx_data.eq(bus.dat_w[:8]),
                                    self.tx_ready.eq(1),
                                ]
                    m.next = "PARK"
            with m.State("PARK"): # TODO i think we can get rid of that FSM, and mark handled instantly.
                comb += self.mark_handled_stmt()
                m.next = "IDLE"

    def elaborate(self, platform: Platform) -> Module:
        m = self.init_owner_module()

        tx_counter = Signal(range(self.divisor))
        m.d.comb += self.tx_strobe.eq(tx_counter == 0)
        with m.If(tx_counter == 0):
            m.d.sync += tx_counter.eq(self.divisor - 1)
        with m.Else():
            m.d.sync += tx_counter.eq(tx_counter - 1)

        self.tx_bitno = tx_bitno = Signal(3)
        self.tx_latch = tx_latch = Signal(8)
        
        self.busy_mmio = busy_mmio = Signal(reset=1)
        
        with m.FSM(reset="IDLE") as self.tx_fsm:
            with m.State("IDLE"):
                m.d.comb += self.tx_ack.eq(1)
                with m.If(self.tx_ready):
                    m.d.sync += [
                        tx_counter.eq(self.divisor - 1),
                        tx_latch.eq(self.tx_data)
                    ]
                    m.next = "START"
                with m.Else():
                    m.d.sync += self.serial.tx.eq(1)
                    m.d.comb += busy_mmio.eq(0)

            with m.State("START"):
                with m.If(self.tx_strobe):
                    m.d.sync += self.serial.tx.eq(0)
                    m.next = "DATA"

            with m.State("DATA"):
                with m.If(self.tx_strobe):
                    m.d.sync += [
                        self.serial.tx.eq(tx_latch[0]),
                        tx_latch.eq(Cat(tx_latch[1:8], 0)),
                        tx_bitno.eq(tx_bitno + 1)
                    ]
                    with m.If(self.tx_bitno == 7):
                        m.next = "STOP"

            with m.State("STOP"):
                with m.If(self.tx_strobe):
                    m.d.sync += self.serial.tx.eq(1)
                    m.next = "IDLE"

        return m

class _LoopbackTest(Elaboratable):
    def __init__(self):
        self.empty = Signal(reset=1)
        self.data = Signal(8)
        self.rx_strobe = Signal()
        self.tx_strobe = Signal()
        self.uart = None

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        serial = platform.request("uart")
        debug = platform.request("debug")

        self.uart = UartTX(serial, clk_freq=12000000, baud_rate=115200)
        m.submodules.uart = self.uart

        arr = Array([Const(ord(x)) for x in "abcxyzpq!\n"])
        max = max=len(arr)
        idx = Signal(max)

        with m.If(self.uart.tx_ack):
            m.d.sync += [
                idx.eq((idx + 1) % max),
                self.uart.tx_data.eq(arr[idx]),
            ]

        m.d.comb += [
            self.tx_strobe.eq(1),
            self.uart.tx_ready.eq(1)
        ]

        m.d.comb += [
            debug.eq(Cat(
                serial.rx,
                serial.tx,
                self.uart.rx_strobe,
                self.uart.tx_strobe,
            ))
        ]

        return m


if __name__ == "__main__":
    plat = ICEBreakerPlatform()

    # The debug pins are on the PMOD1A in the following order on the connector:
    # 7 8 9 10 1 2 3 4
    # Yes that means that the pins at the edge of the board come first
    # and the pins further away from the edge second
    plat.add_resources([
        Resource("debug", 0, Pins("7 8 9 10 1 2 3 4", dir="o",
                                    conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS"))
    ])

    plat.build(_LoopbackTest(), do_program=True)
