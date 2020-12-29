#!/usr/bin/env python3

from nmigen import *

class Mod(Elaboratable):
    def __init__(self, w):
        self.a = Signal(w)
        self.b = Signal()
        
    def elaborate(self, platform):
        m = Module()
        return m

if __name__ == "__main__":
    
    args = parse_args()
    
    
    
    m = Mod(4)

    from nmigen.back.pysim import *
    
    sim = Simulator(m)
    sim.add_clock(1e-6)

    def test():
        # initial value
        assert not (yield m.busy)
        yield m.en.eq(1)
        for i in range(15):
            yield
        yield
        yield
        # a = yield m.out
        # print(a)
        # assert 10 == (yield m.out)

    sim.add_sync_process(test)
    with sim.write_vcd('mod.vcd'):
        sim.run()
        print("=== OK, done")
