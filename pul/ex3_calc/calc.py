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



        return m


if __name__ == "__main__":
    print("dsds")