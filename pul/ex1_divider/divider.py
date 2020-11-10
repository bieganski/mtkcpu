#!/usr/bin/env python3

from nmigen import *
from nmigen.cli import main, pysim

# A divider.  Divides two unsigned numbers, returns quotient and remainder.
class Divider(Elaboratable):
    # `width` is the inputs' width in bits.
    def __init__(self, width):
        self.width = width

        # Inputs.
        # Start trigger for the divider.
        self.start = Signal()
        # Dividend.
        self.a = Signal(width)
        # Divisor.
        self.b = Signal(width)

        # Internal signals.
        self.counter = Signal(range(width))
        self.bit = Signal()
        self.aa = Signal(width)
        self.bb = Signal(width)
        # Outputs.
        # Set if the divider is busy (ie. outputs are *not* ready).
        self.busy = Signal()
        # Quotient.
        self.q = Signal(width)
        # Remainder.
        self.r = Signal(width)
        # Error signal.
        self.err = Signal()

    def elaborate(self, platform):
        m = Module()

        # FILL ME

        with m.If(~self.start & ~self.busy):
            pass # wait for input
        with m.Elif(~self.busy):
            # start the job
            with m.If(self.b == 0):
                m.d.sync += self.err.eq(1)
            with m.Else():
                m.d.sync += self.counter.eq(self.width - 1)
                m.d.sync += self.busy.eq(True)
                m.d.sync += self.r.eq(self.a)
                m.d.sync += self.err.eq(0)
                m.d.sync += self.aa.eq(self.a)
                m.d.sync += self.bb.eq(self.b)
            pass
        with m.Else():
            # continue active job
            m.d.sync += self.counter.eq(self.counter - 1)
            m.d.comb += self.bit.eq(self.r >= (self.bb << self.counter))
            with m.If(self.bit):
                m.d.sync += self.r.eq(self.r - (self.bb << self.counter))
            m.d.sync += self.q.eq((self.q << 1) | self.bit)
            with m.If(self.counter == 0):
                # job finished
                m.d.sync += self.busy.eq(False)
            pass

        return m


if __name__ == '__main__':
    div = Divider(8)
    ports = [
        div.start, div.a, div.b,
        div.busy, div.q, div.r, div.err,
    ]

    import argparse

    parser = argparse.ArgumentParser()
    p_action = parser.add_subparsers(dest="action")
    p_action.add_parser("simulate")
    p_action.add_parser("verilog")
    p_action.add_parser("rtlil")

    args = parser.parse_args()

    if args.action == "simulate":
        from nmigen.back.pysim import *

        sim = Simulator(div)
        sim.add_clock(1e-6)

        def test():
            fail = False
            for a in range(256):
                print(f'{a}...')
                for b in range(256):
                    yield div.a.eq(a)
                    yield div.b.eq(b)
                    yield div.start.eq(1)
                    yield
                    yield div.a.eq(0)
                    yield div.b.eq(0)
                    yield div.start.eq(0)

                    for _ in range(100): # range(100000):
                        yield Settle()
                        if not (yield div.busy):
                            break
                        yield

                    if b == 0:
                        if not (yield div.err):
                            print(f'FAIL — EXPECTED ERROR a={a} b={b}')
                            fail = True
                    else:
                        if (yield div.err):
                            print(f'FAIL — UNEXPECTED ERROR a={a} b={b}')
                            fail = True
                        else:
                            q = a // b
                            r = a % b
                            rq = (yield div.q)
                            rr = (yield div.r)
                            if (q, r) != (rq, rr):
                                fail = True
                                print(f'FAIL — MISMATCH a={a} b={b} q={q} r={r}')
                                print(f'FAIL — MISMATCH a={a} b={b} q={rq} r={rr}')
            if not fail:
                print('PASS')

        sim.add_sync_process(test)

        with sim.write_vcd('div.vcd'):
            sim.run()

    if args.action == "rtlil":
        from nmigen.back import rtlil

        print(rtlil.convert(div, ports=ports))

    if args.action == "verilog":
        from nmigen.back import verilog

        print(verilog.convert(div, ports=ports))
