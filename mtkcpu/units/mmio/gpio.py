from nmigen import *
from typing import List

from mtkcpu.units.loadstore import BusSlaveOwnerInterface, WishboneBusRecord

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

