#!/usr/bin/env python3

from nmigen import *

from serial import AsyncSerialRX
from serial import AsyncSerialTX

from enum import Enum
import math
class Token(Enum):
    PLUS = 0
    MINUS = 1
    MUL = 2
    DIV = 3


class Tokenizer(Elaboratable):
    def __init__(self, word_width):
        self.data_in = Signal(8) # one byte

        self.valid_in = Const(True)
        self.ready_in = Signal()

        self.token_out = Signal(Token)
        self.num_out = Signal(word_width)

        self.valid_out = Signal()
        self.ready_out = Signal()

        self.PLUS  = Const(ord('+'))
        self.MINUS = Const(ord('-'))
        self.MUL   = Const(ord('*'))
        self.DIV   = Const(ord('/'))

        self.MIN_DIGIT = Const(ord('0'))
        self.MAX_DIGIT = Const(ord('9'))

        # for 32-bit width it may take at most 10 cycles for Tokenizer to assert valid_out
        # it is determined by floor $ log10(2**32) value
        self.MAX_DELAY = math.ceil(math.log10(2 ** word_width))

    def is_num_expr(sig):
        return (sig >= self.MIN_DIGIT) & (sig <= self.MAX_DIGIT)

    def elaborate(self, platform):
        pass

class CalcError(Enum):
    Lex = 0
    Parse = 1
    Div = 2
    Overflow = 3
    Serial = 4

def str_to_num_seq(string):
    # ord('a') = 97
    # chr(97) = 'a'
    return Array(map(lambda x: Const(ord(x), 8), string))


ERR_BYTES = {
    CalcError.Lex : str_to_num_seq("ERR LEX\n"),
    CalcError.Parse : str_to_num_seq("ERR PARSE\n"),
    CalcError.Div : str_to_num_seq("ERR DIVIDE\n"),
    CalcError.Overflow : str_to_num_seq("ERR OVERFLOW\n"),
    CalcError.Serial : str_to_num_seq("ERR SERIAL\n"),
}

class Calculator(Elaboratable):
    def __init__(self, clkfreq, baudrate):
        # The frequency of the sync domain in Hz
        self.clkfreq = clkfreq
        # The requested baudrate in bps
        self.baudrate = baudrate

        self.div = int(clkfreq // baudrate)

        # From user to calculator.
        self.rxd = Signal()
        # From calculator to user.
        self.txd = Signal()


    def elaborate(self, platform):
        m = Module()

        comb = m.d.comb
        sync = m.d.sync

        from uart import UartTx, UartRx # written during labs 
        # self.tx = AsyncSerialTX(divisor=self.div, data_bits=8)
        m.submodules.tx = tx = UartTx(divisor=self.div)

        comb += [
            self.txd.eq(tx.txd),
            tx.in_vld.eq(1),
        ]

        idx = Signal(4, reset=-1) # -1 because next is 0
        sync += [
            idx.eq(Mux(
                tx.in_rdy,
                idx + 1,
                idx
            ))
        ]
        # self.tx.in_data.eq(ERR_BYTES[CalcError.Lex][idx])
        # a = Const("hello world\n")
        # a.bit_select(5, 3)
        # letter = ERR_BYTES[CalcError.Lex][idx]
        sync += tx.in_data.eq(ERR_BYTES[CalcError.Lex][idx])
        return m


if __name__ == "__main__":
    clk_freq = 1e+6
    baud = 115200
    div = int(clk_freq // baud)
    calc = Calculator(clk_freq, baud)
    print(div)

    # print(ERR_BYTES[CalcError.Lex])
    # exit(1)
    # tx = AsyncSerialTX(divisor=div)
    # rx = AsyncSerialRX(divisor=div)
    from nmigen.back.pysim import *
    sim = Simulator(calc)
    sim.add_clock(1e-6)

    def test_output():
        for i in range(2000):
            yield

    sim.add_sync_process(test_output)
    # sim.add_sync_process(feed_input)

    with sim.write_vcd('calc.vcd'):
        sim.run()