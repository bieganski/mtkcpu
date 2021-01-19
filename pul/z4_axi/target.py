from nmigen import *


class TargetWrapper(Elaboratable):
    def __init__(self, axi):
        self.axi = axi

        self.rd_stb = Signal()
        self.rd_addr = Signal(32)
        self.rd_data = Signal(32)

        self.wr_stb = Signal()
        self.wr_addr = Signal(32)
        self.wr_data = Signal(32)

    def elaborate(self, platform):
        m = Module()

        # Read path.

        rd_burst = Signal(2)
        rd_size = Signal(2)
        rd_len = Signal(4)
        rd_origlen = Signal(4)
        rd_id = Signal(12)
        rd_ldata = Signal(32)
        rd_hold = Signal()

        m.d.sync += [
            self.rd_stb.eq(0),
        ]

        with m.FSM() as rfsm:
            with m.State('INIT'):
                m.d.comb += [
                    self.axi.ar_ready.eq(1),
                ]
                with m.If(self.axi.ar_valid):
                    m.d.sync += [
                        self.rd_addr.eq(self.axi.ar_addr),
                        self.rd_stb.eq(1),
                        rd_burst.eq(self.axi.ar_burst),
                        rd_size.eq(self.axi.ar_size),
                        rd_len.eq(self.axi.ar_len),
                        rd_origlen.eq(self.axi.ar_len),
                        rd_id.eq(self.axi.ar_id),
                    ]
                    m.next = 'READ'
            with m.State('READ'):
                m.d.comb += [
                    self.axi.r_data.eq(Mux(rd_hold, rd_ldata, self.rd_data)),
                    self.axi.r_id.eq(rd_id),
                    self.axi.r_resp.eq(0),
                    self.axi.r_last.eq(rd_len == 0),
                    self.axi.r_valid.eq(1),
                ]
                with m.If(self.axi.r_ready):
                    with m.If(rd_len == 0):
                        m.next = 'INIT'
                    with m.Else():
                        m.d.sync += [
                            rd_len.eq(rd_len - 1),
                            self.rd_stb.eq(1),
                            rd_hold.eq(0),
                        ]
                        with m.If(rd_burst == 1):
                            m.d.sync += [
                                self.rd_addr.eq(self.rd_addr + (1 << rd_size)),
                            ]
                        with m.Elif(rd_burst == 2):
                            incr = self.rd_addr + (1 << rd_size)
                            slen = (rd_origlen + 1) << rd_size
                            mask = slen - 1
                            m.d.sync += [
                                self.rd_addr.eq(self.rd_addr & ~mask | incr & mask)
                            ]
                with m.Else():
                    m.d.sync += [
                        rd_ldata.eq(self.rd_data),
                        rd_hold.eq(1),
                    ]

        # Write path.

        wr_burst = Signal(2)
        wr_size = Signal(2)
        wr_len = Signal(4)
        wr_origlen = Signal(4)
        wr_id = Signal(12)

        with m.FSM() as wfsm:
            with m.State('INIT'):
                m.d.comb += [
                    self.axi.aw_ready.eq(1),
                ]
                with m.If(self.axi.aw_valid):
                    m.d.sync += [
                        self.wr_addr.eq(self.axi.aw_addr),
                        wr_burst.eq(self.axi.aw_burst),
                        wr_size.eq(self.axi.aw_size),
                        wr_len.eq(self.axi.aw_len),
                        wr_origlen.eq(self.axi.aw_len),
                        wr_id.eq(self.axi.aw_id),
                    ]
                    m.next = 'WRITE'
            with m.State('WRITE'):
                m.d.comb += [
                    self.axi.w_ready.eq(1),
                ]
                with m.If(self.axi.w_valid):
                    m.d.comb += [
                        self.wr_stb.eq(1),
                        self.wr_data.eq(self.axi.w_data),
                    ]
                    with m.If(wr_len == 0):
                        m.next = 'RESP'
                    with m.Else():
                        m.d.sync += [
                            wr_len.eq(wr_len - 1),
                        ]
                        with m.If(wr_burst == 1):
                            m.d.sync += [
                                self.wr_addr.eq(self.wr_addr + (1 << wr_size)),
                            ]
                        with m.Elif(wr_burst == 2):
                            incr = self.wr_addr + (1 << wr_size)
                            slen = (wr_origlen + 1) << wr_size
                            mask = slen - 1
                            m.d.sync += [
                                self.wr_addr.eq(self.wr_addr & ~mask | incr & mask)
                            ]
            with m.State('RESP'):
                m.d.comb += [
                    self.axi.b_valid.eq(1),
                    self.axi.b_id.eq(wr_id),
                    self.axi.b_resp.eq(0),
                ]
                with m.If(self.axi.b_ready):
                    m.next = 'INIT'

        return m

