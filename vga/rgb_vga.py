#!/usr/bin/env python3

from nmigen import *

# TODO - PUL lectures

def elaborate(self, platform):
    m = Module()
    m.domains.sync = DomainSync()
    uclk = platform.request'uclk', 0)
    locked = Signal() # bedziemy uzywac jako resetjako reset
    dcm = m.submodules.dcm = Instance('DCM_SP',
        i_CKLIN=uclk.i,
        i_CLKFB=clk0, # feedback
        o_CLK0=clk0,
        o_CLKFX=ClockSignal('sync'), # nie mozna tu zrobic m.d.sync
        o_LOCKED=locked,
        p_CLKFX_DIVIDE=32,
        p_CLKFX_MULTIPLY=25,
        CLKIN_PERIOD="31.25" # == 1000/32
    )

    m.d.comb += [
        ResetSignal('sync').eq(~locked),
    ]

    vctr = Signal(10)
    hctr = Signal(10)

    with m.If(hctr == 800 - 1):
        sync += [
            hctr.eq(0)
        ]
        with m.If(vctr == 525 - 1):
            sync += [
                vctr.eq(0),
            ]
        with m.Else():
            sync += [
                vctr.eq(vctr + 1),
            ]
    with m.Else():
        sync += [
            hctr.eq(hctr + 1)
        ]

    sync += [
        hsync.o.eq((hctr >= 640 + 16) & (hctr < 640 + 16 + 96)),
        vsync.o.eq((vctr >= 480 + 10 ) & (hctr < 480 + 10 + 2)),
    ]

    active = Signal()
    comb += [
        active.eq((hctr < 640) & (vctr < 480))
    ]

    r = platform.request('vga_r')
    g = platform.request('vga_g')
    b = platform.request('vga_b')

    sync += [
        r.o.eq(Mux(active, hctr[:3], 0)),
        g.o.eq(Mux(active, hctr[:3], 0)),
        b.o.eq(Mux(active, hctr[:3], 0)),
    ]

    return m




class Mod(Elaboratable):
    def __init__(self, w):
        
        self.r = Signal(range(16)) # 16 bit colors
        self.g = Signal(range(16))
        self.b = Signal(range(16))

        self.vsync = Signal(reset=1)
        self.hsync = Signal(reset=1)
        
        self.in_clk = Signal() # from the board, 50 mhz
        # self.out_clk = Signal() # VGA output, 25 mhz

        # http://martin.hinner.info/vga/timing.html
        # 640x480, 60 hz
        self.WIDTH = Const(640)
        self.HEIGHT = Const(4)

        self.H_PORCH_F = Const(16)
        self.H_SYNC_PULSE_F = Const(96) 
        self.H_PORCH_B = Const(48)

        self.V_PORCH_F = Const(11)
        self.V_SYNC_PULSE_F = Const(2)
        self.V_PORCH_B = Const(31)

        self.VSYNC_ACTIVE = Const(0)
        self.HSYNC_ACTIVE = Const(0)

        self.w_pos = Signal(
            (self.WIDTH + self.H_PORCH_F + self.H_SYNC_PULSE_F + self.H_PORCH_F).shape(), 
            reset=0)
        self.h_pos = Signal(
            (self.HEIGHT + self.V_PORCH_F + self.V_SYNC_PULSE_F + self.V_PORCH_F).shape(), 
            reset=0)

        self.total_width = Signal(self.w_pos.shape()) # 640 + 16 + 96 + 48 = (800)
        self.total_height = Signal(self.h_pos.shape()) # 4 + 11 + 2 + 31 = (48), normally with 480 it's (524) 

        self.rst = Signal()

        
    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d.sync # TODO wrong domain

        comb += [
            self.total_width.eq(self.WIDTH + self.H_PORCH_F + self.H_SYNC_PULSE_F + self.H_PORCH_B),
            self.total_height.eq(self.HEIGHT + self.V_PORCH_F + self.V_SYNC_PULSE_F + self.V_PORCH_B),
            
            # TODO drugi cond byc moze +-1
            self.hsync.eq(Mux(
                (self.w_pos >= self.WIDTH + self.H_PORCH_F) & (self.w_pos < self.total_width - self.H_PORCH_B),
                self.HSYNC_ACTIVE,
                ~self.HSYNC_ACTIVE
            )),
            self.vsync.eq(Mux(
                (self.h_pos >= self.HEIGHT + self.V_PORCH_F) & (self.h_pos < self.total_height - self.V_PORCH_B),
                self.VSYNC_ACTIVE,
                ~self.VSYNC_ACTIVE
            )),
        ]

        # hsync
        with m.If(self.w_pos < self.total_width - 1):
            # line end
            sync += self.w_pos.eq(self.w_pos + 1)
        with m.Else():
            sync += self.w_pos.eq(0)

        # vsync
        with m.If(self.w_pos == self.WIDTH - 1):
            # line end
            with m.If(self.h_pos < self.total_height - 1):
                sync += self.h_pos.eq(self.h_pos + 1)
            with m.Else():
                sync += self.h_pos.eq(0)


        with m.If(self.w_pos < (self.WIDTH >> 1)):
            sync += self.r.eq(15)
            sync += self.g.eq(0)
            sync += self.b.eq(0)
        with m.Else():
            sync += self.r.eq(0)
            sync += self.g.eq(15)
            sync += self.b.eq(0)

        return m



if __name__ == "__main__":
    
    m = Mod(4)

    ports = [
        # m.out_clk,
        m.r,
        m.g,
        m.b,
    ]

    from nmigen.back.pysim import *
    
    sim = Simulator(m)
    sim.add_clock(1e-6)

    def test():
        # initial value
        # assert not (yield m.busy)
        # yield m.en.eq(1)
        # for i in range(26000000):
        for i in range(641 * 4 + 40000):
            yield
        # a = yield m.out
        # print(a)
        # assert 10 == (yield m.out)

    from nmigen.back import rtlil
    a = open("mod.il", "w")
    a.write(rtlil.convert(m, ports=ports))
    print("=== OK, mod.il written")

    from nmigen.back import verilog
    a = open("mod.v", "w")
    a.write(verilog.convert(m, ports=ports))
    print("=== OK, mod.v written")

    sim.add_sync_process(test)
    with sim.write_vcd('mod.vcd'):
        sim.run()
        print("=== OK, sim done")
