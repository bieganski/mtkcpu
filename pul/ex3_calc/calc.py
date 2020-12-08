#!/usr/bin/env python3

from nmigen import *

from serial import AsyncSerialRX
from serial import AsyncSerialTX

class Calculator(Elaboratable):
    def __init__(self, clkfreq, baudrate):
        # The frequency of the sync domain in Hz
        self.clkfreq = clkfreq
        # The requested baudrate in bps
        self.baudrate = baudrate

        # From user to calculator.
        self.rxd = Signal()
        # From calculator to user.
        self.txd = Signal()

    def elaborate(self, platform):
        m = Module()

        comb = m.d.comb
        sync = m.d.sync

        sync += [
            self.txd.eq(1)
        ]
        
        return m


if __name__ == "__main__":
    calc = Calculator(1e-6, 115200) # 1 mhz, 115.200 UART baud rate
    from nmigen.back.pysim import *
    sim = Simulator(calc)
    sim.add_clock(1e-6)

    def test_output():
        for i in range(100):
            yield

    sim.add_sync_process(test_output)
    # sim.add_sync_process(feed_input)

    with sim.write_vcd('calc.vcd'):
        sim.run()