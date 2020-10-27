#!/usr/bin/env python3
from nmigen import *
from nmigen.cli import main, pysim

# A counter that counts down to 0.
class Counter(Elaboratable):
    # Width is the counter's width in bits.
    def __init__(self, width):
        # Inputs.
        # Start trigger for the counter.
        self.start = Signal()
        # Start value of the counter.
        self.startval = Signal(width)
        # Counter enable — if 0, the counter will be paused.
        self.en = Signal(reset=True)

        # Outputs.
        # Set if the counter is done counting (the count is 0).
        self.done = Signal()

        # Internal state.
        # Current counter value
        self.val = Signal(width)

    def elaborate(self, platform):
        m = Module()

        with m.If(self.start):
            m.d.sync += self.val.eq(self.startval)
        with m.Elif(self.en & (self.val != 0)):
            m.d.sync += self.val.eq(self.val - 1)

        m.d.comb += self.done.eq(self.val == 0)

        return m


if __name__ == '__main__':
    ctr = Counter(4)
    ports = [
        ctr.start, ctr.startval, ctr.en,
        ctr.done,
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

        sim = Simulator(ctr)
        sim.add_clock(1e-6)

        def test():
            # Initially the counter is 0.
            assert (yield ctr.done)

            # Still 0 after one cycle.
            yield
            assert (yield ctr.done)

            # Start it.
            yield ctr.startval.eq(3)
            yield ctr.start.eq(1)
            yield
            yield ctr.start.eq(0)

            # Will be non-0 for 3 cycles.
            for _ in range(3):
                yield Settle()
                assert not (yield ctr.done)
                yield

            # Now it's 0.
            yield Settle()
            assert (yield ctr.done)

            # Start it again.
            yield ctr.start.eq(1)
            yield
            yield ctr.start.eq(0)

            # Step it.
            yield

            # Disable it.
            yield ctr.en.eq(0)

            # It will not advance.
            for _ in range(10):
                yield
                yield Settle()
                assert not (yield ctr.done)

            # Reenable.
            yield ctr.en.eq(1)

            # Will be non-0 for 2 cycles.
            for _ in range(2):
                yield Settle()
                assert not (yield ctr.done)
                yield

            # Now it's 0.
            yield Settle()
            assert (yield ctr.done)

        sim.add_sync_process(test)

        with sim.write_vcd('ctr.vcd'):
            sim.run()

    if args.action == "rtlil":
        from nmigen.back import rtlil

        print(rtlil.convert(ctr, ports=ports))

    if args.action == "verilog":
        from nmigen.back import verilog

        print(verilog.convert(ctr, ports=ports))
