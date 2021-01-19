from nmigen import *
from nmigen.lib.fifo import SyncFIFO


class Writer(Elaboratable):
    def __init__(self, axi):
        self.axi = axi

        self.trigger = Signal()
        self.addr = Signal(32)
        self.count = Signal(32)
        self.busy = Signal()
        self.error = Signal()

        self.in_data = Signal(64)
        self.in_vld = Signal()
        self.in_rdy = Signal()

        self.counters = [
                Signal(32),
                Signal(32),
                Signal(32),
                Signal(32),
        ]

    def elaborate(self, platform):
        m = Module()

        m.submodules.fifo = fifo = SyncFIFO(width=64, depth=64)

        reqctr = Signal(32)
        pendctr = Signal(32)
        ackctr = Signal(32)
        ackinc = Signal()
        wrctr = Signal(32)
        wrinc = Signal(32)
        addr = Signal(32)

        reqctr = self.counters[0]
        pendctr = self.counters[1]
        wrctr = self.counters[2]
        ackctr = self.counters[3]

        m.d.comb += [
            self.busy.eq((reqctr != 0) | (pendctr != 0) | (ackctr != 0))
        ]

        with m.If(self.trigger & ~self.busy):
            m.d.sync += [
                reqctr.eq(self.count),
                addr.eq(self.addr),
                self.error.eq(0),
            ]

        # Request.

        m.d.comb += [
            self.axi.aw_burst.eq(1),
            self.axi.aw_size.eq(3),
            self.axi.aw_len.eq(0),
            self.axi.aw_lock.eq(0),
            self.axi.aw_prot.eq(0),
            self.axi.aw_cache.eq(0),
            self.axi.aw_qos.eq(0),
            self.axi.aw_id.eq(0),
            self.axi.aw_addr.eq(addr),
        ]
        with m.If((reqctr != 0) & (pendctr != 0)):
            m.d.comb += [
                self.axi.aw_valid.eq(1),
            ]
            with m.If(self.axi.aw_ready):
                m.d.comb += [
                    ackinc.eq(1)
                ]
                m.d.sync += [
                    addr.eq(addr + 8),
                    reqctr.eq(reqctr - 1),
                ]
                m.d.comb += [
                    wrinc.eq(1)
                ]

        # Response.

        m.d.comb += [
            self.axi.b_ready.eq(ackctr != 0),
        ]

        with m.If(self.axi.b_valid & self.axi.b_ready):
            m.d.sync += [
                ackctr.eq(ackctr+ackinc-1)
            ]
            with m.If(self.axi.b_resp != 0):
                m.d.sync += [
                    self.error.eq(1),
                ]
        with m.Else():
            m.d.sync += [
                ackctr.eq(ackctr+ackinc)
            ]

        # Data from FIFO to AXI.

        with m.If(wrctr != 0):
            m.d.comb += [
                self.axi.w_valid.eq(fifo.r_rdy),
                fifo.r_en.eq(self.axi.w_ready),
            ]

        m.d.comb += [
            self.axi.w_data.eq(fifo.r_data),
            self.axi.w_last.eq(1),
            self.axi.w_id.eq(0),
            self.axi.w_strb.eq(0xff),
        ]

        with m.If(self.axi.w_valid & self.axi.w_ready):
            m.d.sync += [
                wrctr.eq(wrctr + wrinc - 1),
            ]
        with m.Else():
            m.d.sync += [
                wrctr.eq(wrctr + wrinc),
            ]

        # Data to FIFO.

        m.d.comb += [
            fifo.w_data.eq(self.in_data),
            fifo.w_en.eq(self.in_vld),
            self.in_rdy.eq(fifo.w_rdy)
        ]

        with m.If(self.in_vld & self.in_rdy):
            m.d.sync += [
                pendctr.eq(pendctr - wrinc + 1),
            ]
        with m.Else():
            m.d.sync += [
                pendctr.eq(pendctr - wrinc),
            ]

        return m
