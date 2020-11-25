#!/usr/bin/env python3

from nmigen import *


WIDTH = 640
HEIGHT = 480

class Mod(Elaboratable):
    def __init__(self, w):
        
        self.r = Signal(range(16)) # 16 bit colors
        self.g = Signal(range(16))
        self.b = Signal(range(16))

        self.vsync = Signal()
        self.hsync = Signal()
        
        self.in_clk = Signal() # from the board, 50 mhz
        self.out_clk = Signal() # VGA output, 25 mhz

        self.w_pos = Signal(range(WIDTH))
        self.h_pos = Signal(range(HEIGHT))

        self.rst = Signal()

        
    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d.sync

        comb += [
            self.hsync.eq(~ (self.w_pos <= WIDTH)),
            self.vsync.eq(~ (self.h_pos <= HEIGHT)),
        ]

        sync += self.rst.eq(True)
        return m



if __name__ == "__main__":
    
    m = Mod(4)

    ports = [
        m.out_clk,
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
        for i in range(22):
            yield
        # a = yield m.out
        # print(a)
        # assert 10 == (yield m.out)

    sim.add_sync_process(test)
    with sim.write_vcd('mod.vcd'):
        sim.run()
        print("=== OK, sim done")

    from nmigen.back import rtlil
    a = open("mod.il", "w")
    a.write(rtlil.convert(m, ports=ports))
    print("=== OK, mod.il written")

    from nmigen.back import verilog
    a = open("mod.v", "w")
    a.write(verilog.convert(m, ports=ports))
    print("=== OK, mod.v written")
