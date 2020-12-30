#!/usr/bin/env python3

from nmigen import *

class Mod(Elaboratable):
    def __init__(self, w):
        self.a = Signal(w)
        self.b = Signal()
        
    def elaborate(self, platform):
        m = Module()
        sync = m.d.sync

        # #### change these

        from nmigen.lib.fifo import SyncFIFO
        m.submodules.fifo = fifo = SyncFIFO(width=8, depth=4)
        

        a = Signal(8, reset=1)
        sync += a.eq(a + 1)

        sync += [
            fifo.w_data.eq(a),
            fifo.w_en.eq(1),
            # fifo.w_data.eq(a),
            fifo.r_en.eq(1),
        ]
        
        # #### 

        return m

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

    sim.add_sync_process(test)
    with sim.write_vcd('mod.vcd'):
        sim.run()
        print("=== OK, done")
