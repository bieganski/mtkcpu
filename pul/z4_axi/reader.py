from nmigen import *
from nmigen.lib.fifo import SyncFIFO


class Reader(Elaboratable):
    def __init__(self, axi):
        self.axi = axi

        self.trigger = Signal()
        self.addr = Signal(32)
        self.count = Signal(32)
        self.busy = Signal()
        self.error = Signal()

        self.out_data = Signal(64)
        self.out_vld = Signal()
        self.out_rdy = Signal()

    def elaborate(self, platform):
        m = Module()

        m.submodules.fifo = fifo = SyncFIFO(width=64, depth=64)

        reqctr = Signal(32)
        repctr = Signal(32)
        repinc = Signal(32)
        addr = Signal(32)

        m.d.comb += [
            self.busy.eq((reqctr != 0) | (repctr != 0))
        ]

        with m.If(self.trigger & ~self.busy):
            m.d.sync += [
                reqctr.eq(self.count),
                addr.eq(self.addr),
                self.error.eq(0),
            ]

        m.d.comb += [
            self.axi.ar_burst.eq(1),
            self.axi.ar_size.eq(3),
            self.axi.ar_len.eq(0),
            self.axi.ar_lock.eq(0),
            self.axi.ar_prot.eq(0),
            self.axi.ar_cache.eq(0),
            self.axi.ar_qos.eq(0),
            self.axi.ar_id.eq(0),
            self.axi.ar_addr.eq(addr),
        ]
        with m.If((reqctr != 0) & (repctr <= 63)):
            m.d.comb += [
                self.axi.ar_valid.eq(1),
            ]
            with m.If(self.axi.ar_ready):
                m.d.sync += [
                    addr.eq(addr + 8),
                    reqctr.eq(reqctr - 1),
                ]
                m.d.comb += [
                    repinc.eq(1),
                ]

        m.d.comb += [
            fifo.w_data.eq(self.axi.r_data),
            fifo.w_en.eq(self.axi.r_valid),
            self.axi.r_ready.eq(fifo.w_rdy)
        ]

        with m.If(self.axi.r_valid & self.axi.r_ready):
            with m.If(self.axi.r_resp != 0):
                m.d.sync += [
                    self.error.eq(1),
                ]

        m.d.comb += [
            self.out_vld.eq(fifo.r_rdy),
            self.out_data.eq(fifo.r_data),
            fifo.r_en.eq(self.out_rdy),
        ]

        with m.If(self.out_vld & self.out_rdy):
            m.d.sync += [
                repctr.eq(repctr + repinc - 1),
            ]
        with m.Else():
            m.d.sync += [
                repctr.eq(repctr + repinc),
            ]

        return m
