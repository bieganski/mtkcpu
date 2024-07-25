from amaranth import *

from mtkcpu.utils.common import EBRMemConfig
from mtkcpu.units.loadstore import BusSlaveOwnerInterface, WishboneBusRecord


class EBR_Wishbone(Elaboratable, BusSlaveOwnerInterface):
    def __init__(self, mem_config : EBRMemConfig) -> None:
        BusSlaveOwnerInterface.__init__(self)
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

        # from math import log2
        # ws_bytes = self.mem_config.word_size
        # assert log2(ws_bytes).is_integer()
        # ws_bit_shift = Const(int(log2(ws_bytes)))
        # # raise ValueError(ws_bit_shift)

        # real_addr = Signal(32)
        # wb_comb += real_addr.eq(addr >> ws_bit_shift)

        real_addr = Signal(32)
        wb_comb += real_addr.eq(addr >> 2) 

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
