#!/usr/bin/env python3

from nmigen import *

class MModule(Elaboratable):
    def __init__(self, witdth):
        pass
    def elaborate(self, platform):
        pass
    
if __name__ == "__main__":
        m = Module()

        a = Signal(4)
        b = Signal(4)
        c = Signal(4)
        y = Signal(4)
        m.d.comb += Cat(y).eq(a+b+c)

        ports = [a, b, c, y]

        from nmigen.back import rtlil

        print(rtlil.convert(m, ports=ports))
