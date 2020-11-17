#!/usr/bin/env python3

from nmigen import *

class UART(Elaboratable):
    def __init__(self, parity=False):
        self.parity = Signal(reset=parity)
        
    def elaborate(self, platform):
        m = Module()
        return m

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
    
    sync = m.d.sync
    comb = m.d.comb
    
    
    m = UART(True)
    # ports = [m.a, m.b, m.out]

    if args.action == "rtlil":
        from nmigen.back import rtlil
        print(rtlil.convert(m, ports=ports))
        exit()

    from nmigen.back.pysim import *
    
    sim = Simulator(m)
    sim.add_clock(1e-6)

    def test():
     #   assert not (yield m.busy)

        yield

    sim.add_sync_process(test)
    with sim.write_vcd('uart.vcd'):
        sim.run()
        print("=== OK, done")
