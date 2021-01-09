#!/usr/bin/env python3

from nmigen import *


class Mod(Elaboratable):
    def __init__(self, w):
        self.a = Signal(w)
        self.b = Signal()
        self.wtf = 2134
        
    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb 
        sync = m.d.sync
        
        a = Signal(8, reset=0)
        b = Signal(8, reset=0)

        x = Cat([1,1,1,0,0])
        c = Signal(8)
        sync += [
            c.eq(x),
            a.eq(0xf),
            b.eq(Cat([1,1,1,0,0], a)),
        ]

        return m

# m = Mod(32)
# b = [(getattr(m, x), x) for x in dir(m) if type(getattr(m, x)) == Signal]
# print(b)
# exit(1)

if __name__ == "__main__":
    
    
    m = Mod(4)

    from nmigen.back.pysim import *
    
    sim = Simulator(m)
    sim.add_clock(1e-6)

    def test():
        # initial value
        # assert not (yield m.busy)
        # yield m.en.eq(1)
        for i in range(15):
            yield
        yield
        yield
        # a = yield m.out
        # print(a)
        # assert 10 == (yield m.out)

    ports = [
        m.b, # m.lol.a
    ]

    sim.add_sync_process(test)
    with sim.write_vcd('mod.vcd'):
        sim.run()
        # print("=== OK, done")
    from nmigen.back import verilog
    print(verilog.convert(m, ports=ports))
