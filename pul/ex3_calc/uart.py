from nmigen import *
from nmigen.lib.cdc import FFSynchronizer

import random
from enum import Enum

class UartTx(Elaboratable):
    def __init__(self, divisor):
        self.divisor = divisor

        # Input FIFO.
        self.in_rdy = Signal()
        self.in_vld = Signal()
        self.in_data = Signal(8)

        # Serial data output.
        self.txd = Signal(reset=1)

    def elaborate(self, platform):
        m = Module()

        data = Signal(10)
        pos = Signal(range(10))
        counter = Signal(range(self.divisor))

        with m.FSM() as fsm:
            with m.State('IDLE'):
                m.d.comb += self.in_rdy.eq(1)
                m.d.sync += self.txd.eq(1)
                with m.If(self.in_vld):
                    m.d.sync += data.eq(Cat(C(0, 1), self.in_data, C(1, 1)))
                    m.d.sync += counter.eq(self.divisor - 1)
                    m.d.sync += pos.eq(0)
                    m.next = 'DATA'
            with m.State('DATA'):
                m.d.sync += self.txd.eq(data[0])
                with m.If(counter == 0):
                    m.d.sync += counter.eq(self.divisor - 1)
                    with m.If(pos == 9):
                        m.next = 'IDLE'
                    with m.Else():
                        m.d.sync += pos.eq(pos + 1)
                        m.d.sync += data.eq(data >> 1)
                        m.next = 'DATA'
                with m.Else():
                    m.d.sync += counter.eq(counter - 1)

        return m


class RxErrCode(Enum):
    OK = 0
    OVERFLOW = 1
    START_ERR = 2
    STOP_ERR = 3


class UartRx(Elaboratable):
    def __init__(self, divisor):
        self.divisor = divisor

        # Output FIFO.
        self.out_rdy = Signal()
        self.out_vld = Signal()
        self.out_data = Signal(8)
        self.out_err = Signal(RxErrCode)

        # Serial data input.
        self.rxd = Signal()

    def elaborate(self, platform):
        m = Module()

        counter = Signal(range(self.divisor))
        pos = Signal(range(8))
        data = Signal(8)
        err = Signal(RxErrCode)
        done = Signal()
        rxd_s = Signal()
        m.submodules.rxd_sync = FFSynchronizer(self.rxd, rxd_s, reset=1)
        with m.FSM() as fsm:
            with m.State('IDLE'):
                with m.If(rxd_s == 0):
                    m.d.sync += counter.eq(self.divisor // 2 - 1)
                    m.next = 'START'
            with m.State('START'):
                with m.If(counter == 0):
                    with m.If(rxd_s == 0):
                        m.d.sync += counter.eq(self.divisor - 1)
                        m.d.sync += pos.eq(0)
                        m.next = 'DATA'
                    with m.Else():
                        m.d.comb += err.eq(RxErrCode.START_ERR)
                        m.d.comb += done.eq(1)
                        m.next = 'IDLE'
                with m.Else():
                    m.d.sync += counter.eq(counter-1)
            with m.State('DATA'):
                with m.If(counter == 0):
                    m.d.sync += data.eq(Cat(data[1:8], rxd_s))
                    with m.If(pos == 7):
                        m.d.sync += counter.eq(self.divisor - 1)
                        m.next = 'STOP'
                    with m.Else():
                        m.d.sync += counter.eq(self.divisor - 1)
                        m.d.sync += pos.eq(pos + 1)
                with m.Else():
                    m.d.sync += counter.eq(counter-1)
            with m.State('STOP'):
                with m.If(counter == 0):
                    with m.If(rxd_s == 1):
                        m.d.comb += err.eq(RxErrCode.OK)
                        m.d.comb += done.eq(1)
                        m.next = 'IDLE'
                    with m.Else():
                        m.d.comb += err.eq(RxErrCode.STOP_ERR)
                        m.d.comb += done.eq(1)
                        m.next = 'IDLE'
                with m.Else():
                    m.d.sync += counter.eq(counter-1)

        with m.If(done):
            with m.If(self.out_vld & ~self.out_rdy):
                m.d.sync += self.out_err.eq(RxErrCode.OVERFLOW)
            with m.Else():
                m.d.sync += [
                    self.out_vld.eq(1),
                    self.out_data.eq(data),
                    self.out_err.eq(err),
                ]
        with m.Else():
            with m.If(self.out_vld & self.out_rdy):
                m.d.sync += self.out_vld.eq(0)

        return m


if __name__ == '__main__':
    divisor = round((1 / 1e-7) / 115200)
    m = Module()
    print(divisor)
    m.submodules.tx = tx = UartTx(divisor)
    m.submodules.rx = rx = UartRx(divisor)
    m.d.comb += rx.rxd.eq(tx.txd)
    ports = [
        tx.in_rdy, tx.in_vld, tx.in_data,
        rx.out_rdy, rx.out_vld, rx.out_data, rx.out_err,
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

        sim = Simulator(m)
        sim.add_clock(1e-7)

        in_data = b'Hello, world!\n'

        def feed_input():
            yield
            idx = 0
            while idx < len(in_data):
                if random.randrange(1000) != 0:
                #if 0:
                    yield tx.in_vld.eq(0)
                    yield
                else:
                    yield tx.in_vld.eq(1)
                    yield tx.in_data.eq(in_data[idx])
                    yield
                    if (yield tx.in_rdy):
                        idx += 1
            yield tx.in_vld.eq(0)

        def print_output():
            yield
            yield Settle()
            idx = 0
            while idx < len(in_data):
                #if random.randrange(8) == 0:
                if 0:
                    yield rx.out_rdy.eq(0)
                    yield
                else:
                    yield rx.out_rdy.eq(1)
                    yield
                    if (yield rx.out_vld):
                        data = (yield rx.out_data)
                        err = (yield rx.out_err)
                        print('RECV', RxErrCode(err).name, chr(data))
                        idx += 1

        sim.add_sync_process(feed_input)
        sim.add_sync_process(print_output)

        with sim.write_vcd('uart.vcd'):
            sim.run()

    if args.action == "rtlil":
        from nmigen.back import rtlil

        print(rtlil.convert(m, ports=ports))

    if args.action == "verilog":
        from nmigen.back import verilog

        print(verilog.convert(m, ports=ports))
