from nmigen import *

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

        # FILL ME

        return m
