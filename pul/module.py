#!/usr/bin/env python3

from nmigen import *

class Multiplier(Elaboratable):
    def __init__(self, w):
        self.a = Signal(w)
        self.b = Signal(w)
        self.bb = Signal(2 * w)
        self.busy = Signal()
        self.en = Signal()
        self.tmp = Signal(w)
        self.bit = Signal()
        self.out = Signal(2 * w)
        self.counter = Signal(w, reset=1)
        self.w = w
        
    def elaborate(self, platform):
        m = Module()
        # tmp = Signal()
        
        with m.FSM() as fsm:
            with m.State('START'):
                m.d.sync += self.tmp.eq(self.a)
                m.d.sync += self.bb.eq(self.b)
                with m.If(self.en):
                    m.next = 'LOOP'
                with m.Else():
                    m.next = 'START'
            with m.State('LOOP'):
                m.d.sync += self.counter.eq(self.counter + 1)
                m.d.comb += self.bit.eq(self.tmp[0])
                m.d.sync += self.tmp.eq(self.tmp >> 1)
                m.d.sync += self.bb.eq(self.bb << 1)
                with m.If(self.bit):
                    m.d.sync += self.out.eq(self.out + self.bb)
                with m.If(self.counter == self.w):
                    m.next = 'END'
                with m.Else():
                    m.next = 'LOOP'
            with m.State('END'):
                m.d.sync += self.out.eq(111)
        return m

'''
        with m.If(self.en):
            m.d.comb += self.tmp.eq(self.a)
            m.d.sync += self.busy.eq(1)
            m.d.sync += self.out.eq(self.a *  self.b)
        with m.Else():
            m.d.sync += self.busy.eq(0)
        # m.d.comb += self.out.eq(self.a * self.b)
        return m
 '''

def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    p_action = parser.add_subparsers(dest="action")
    p_action.add_parser("simulate")
    p_action.add_parser("verilog")
    p_action.add_parser("rtlil")

    return parser.parse_args()

if __name__ == "__main__":
    
    args = parse_args()
    
    
    
    m = Multiplier(4)
    ports = [m.a, m.b, m.out]

    if args.action == "rtlil":
        from nmigen.back import rtlil
        print(rtlil.convert(m, ports=ports))
        exit()

    from nmigen.back.pysim import *
    
    sim = Simulator(m)
    sim.add_clock(1e-6)

    def test():
        # initial value
        assert not (yield m.busy)

        yield m.a.eq(5)
        yield m.b.eq(2)
        yield
        yield
        yield m.en.eq(1)
        for i in range(15):
            yield
        yield
        yield
        # a = yield m.out
        # print(a)
        # assert 10 == (yield m.out)

    sim.add_sync_process(test)
    with sim.write_vcd('mul.vcd'):
        sim.run()
        print("=== OK, done")
