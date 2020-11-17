#!/usr/bin/env python3

from nmigen import *
from enum import Enum

class RxError(Enum):
    OK = 0
    OVERFLOW = 1
    START_ERR = 2




class UartRx(Elaboratable):
    def __init__(self, divisor):
        self.divisor = divisor

        self.out_rdy = Signal()
        self.out_vld = Signal()
        self.out_data = Signal(8)
        self.data = Signal(8)
        self.out_err = Signal(RxError)

        self.rxd = Signal(reset=True)
        
    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d.sync
        done = Signal()

        counter = Signal(range(self.divisor))
        with m.FSM() as fsm:
            with m.State('IDLE'):
                with m.If(self.rxd == 0):
                    sync += counter.eq(self.divisor//2 - 1)
                    m.next = 'START'
            with m.State('START'):
                # receive start bit
                with m.If(counter == 0):
                    with m.If(self.rxd == 0):
                        sync += counter.eq(self.divisor - 1)
                        sync += pos.eq(0)
                        m.next = 'DATA'
                    with m.Else():
                        comb += self.out_err.eq(RxError.START_ERR)
                        comb += done.eq(1)
                with m.Else():
                    sync += counter.eq(counter - 1)
            with m.State('DATA'):
                # receive start bit
                with m.If(counter == 0):
                    sync += self.data.eq(Cat(self.data[7:1], self.rxd))
                    with m.If(pos == 7):
                        sync += counter.eq(self.divisor - 1)
                        m.next = 'STOP'
                with m.Else():
                    sync += counter.eq(counter - 1)
            with m.State('DATA'):
                # receive start bit
                with m.If(counter == 0):
                    sync += self.data.eq()
                with m.Else():
                    pass

            with m.If(done):
                with m.If(self.out_vld & ~self.out_rdy):
                    sync += self.out_err.eq(RxError.OVERFLOW)
                with m.Else():
                    sync += [
                        self.out_vld.eq(True),
                        self.out_data.eq(data),
                        self.out_err.eq(err)
                    ]
            with m.Else():
                with m.If(self.out_vld & ~self.out_rdy):
                    sync += self.out_vld.eq(False)
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
    m = Module()
    m.submodules += rx = UartRx(divisor)
    m.submodules += tx = UartTx(divisor)
    m.d.comb += rx.rxd.connect(tx.txd)
    
    args = parse_args()
    
    sync = m.d.sync
    comb = m.d.comb
    
    
    m = UartRx(True)
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
