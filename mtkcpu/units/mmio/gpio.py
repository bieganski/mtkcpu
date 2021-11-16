from argparse import ArgumentError
from nmigen import *
from typing import List, Callable

from nmigen.build import Platform

from mtkcpu.units.loadstore import BusSlaveOwnerInterface
from mtkcpu.units.mmio.bspgen import BspGeneratable
from mtkcpu.units.memory_interface import MMIOPeriphConfig, MMIORegister

class GPIO_Wishbone(Elaboratable, BusSlaveOwnerInterface, BspGeneratable):
    def __init__(self) -> None:
        raise ArgumentError()

    def __init__(self, signal_map_gen : Callable[[Platform], List[Signal]]) -> None:
        BusSlaveOwnerInterface.__init__(self)
        self.signal_map_gen = signal_map_gen

    def sanity_check(self):
        signal_map = self.signal_map
        if len(signal_map) > 32:
            raise ValueError(f"Error: for now GPIO supports at most 32 signals, passed {len(signal_map)}")
        if len(signal_map) == 0:
            raise ValueError(f"Error: empty GPIO signal map passed! Disable it if not used.")

    def get_periph_config(self) -> MMIOPeriphConfig:
        bits=[
            (s.name, i) for i, s in enumerate(self.signal_map) if isinstance(s, Signal)
        ]
        # platform.request returns Record instance.
        # TODO will throw KeyError in case of input signal
        bits += [
            (r['o'].name, i) for i, r in enumerate(self.signal_map) if isinstance(r, Record)
        ]

        cfg = MMIOPeriphConfig(
            regions=[],
            registers=[
                MMIORegister(
                    name="gpio_state",
                    addr=0x0,
                    description="State of all GPIO signals (either high or low).",
                    bits=bits
                ),
            ],
        )
        return cfg

    def elaborate(self, platform):
        self.signal_map = self.signal_map_gen(platform)
        self.sanity_check()
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

        # NOTE
        # we cannot use 'comb' domain here, as we are in 'transaction' context, 
        # so the assignments won't be persistent.
        for i, s in enumerate(self.signal_map):
            if isinstance(s, Signal):
                if s.width != 1:
                    raise ValueError("GPIO: only single bits signals supported!")
                sync += s.eq(gpio_output[i])
            elif isinstance(s, Record):
                if len(s.fields) > 1:
                    print(f"ERROR: as part of sigal_map param GPIO received Record instance with more than 1 field! ({len(s.fields)})")
                    exit(1)
                fs = s.fields
                sig_o = fs.get('o', None)
                sig_i = fs.get('i', None)
                if isinstance(sig_o, Signal):
                    print(f"GPIO: adding output {sig_o} to GPIO pin {i}..")
                    sync += sig_o.eq(gpio_output[i])
                elif isinstance(sig_i, Signal):
                    print(f"GPIO: adding input {sig_i} to GPIO pin {i}..")
                    sync += gpio_output[i].eq(sig_i)
                else:
                    print(f"ERROR: as part of sigal_map param GPIO received Record instance without 'o' or 'i' field! {fs}")
            else:
                print(f"GPIO: skipping non-signal value at index {i}..")

        with m.FSM():
            with m.State("GPIO_REQ"):
                with m.If(cyc & (addr == 0x0)):
                    with m.If(write):
                        # sync += gpio_output[0:2].eq(Const(0b11, 2)) # XXX REMOVE ME
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

