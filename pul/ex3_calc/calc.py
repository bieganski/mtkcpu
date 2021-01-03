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
    NUM = 4
    PARENTHESIS = 5
    END = 6

class CalcError(Enum):
    Lex = 0
    Parse = 1
    Div = 2
    Overflow = 3
    Serial = 4
    Internal = 5
    Ok = 6

PLUS          = Const(ord('+'), 8)
MINUS         = Const(ord('-'), 8)
MUL           = Const(ord('*'), 8)
DIV           = Const(ord('/'), 8)

LEFT_PARENTH  = Const(ord('('), 8)
RIGHT_PARENTH = Const(ord(')'), 8)

MIN_DIGIT     = Const(ord('0'), 8)
MAX_DIGIT     = Const(ord('9'), 8)

NEW_LINE      = Const(ord('\n'), 8)
SPACE         = Const(ord(' '),  8)
TAB           = Const(ord('\t'), 8)

# Const is not hashable, cannot use dict
def sig_token_type(m, domain, sig):
    ret = Signal(Token, name="ret_token")
    with m.If(sig == PLUS):
        domain += ret.eq(Token.PLUS)
    with m.Elif(sig == MINUS): 
        domain += ret.eq(Token.MINUS)
    with m.Elif(sig == MUL): 
        domain += ret.eq(Token.MUL)
    with m.Elif(sig == DIV):
        domain += ret.eq(Token.DIV)
    with m.Elif(sig == LEFT_PARENTH): 
        domain += ret.eq(Token.PARENTHESIS)
    with m.Elif(sig == RIGHT_PARENTH): 
        domain += ret.eq(Token.PARENTHESIS)
    with m.Else():
        # TODO somehow assert False
        pass
    return ret

def is_white(sig):
    return (sig == SPACE) | (sig == TAB)

def is_digit(sig):
    return (sig >= MIN_DIGIT) & (sig <= MAX_DIGIT)

def digit_sig_to_val(digit_sig):
    return digit_sig - Const(ord('0'), 8)

def is_parenthesis(sig):
    return (sig == LEFT_PARENTH) | (sig == RIGHT_PARENTH)

def is_op(sig):
    return (sig == PLUS) | (sig == MINUS) | (sig == MUL) | (sig == DIV)

def is_newline(sig):
    return sig == NEW_LINE


from nmigen.lib.fifo import SyncFIFO

class Tokenizer(Elaboratable):
    def __init__(self):
        self.in_vld = Signal(reset=0)
        self.in_rdy = Signal(reset=1)
        self.in_data = Signal(8) # one byte, from UART RX

        self.out_type = Signal(Token)
        self.out_data = Signal(32)

        self.out_vld = Signal()
        self.out_rdy = Signal()

        self.err = Signal(CalcError, reset=CalcError.Ok)

        # for 32-bit width it may take at most 10 cycles for Tokenizer to assert valid_out
        # it is determined by floor $ log10(2**32) value
        self.MAX_DELAY = math.ceil(math.log10(2 ** 32))
        
        self.FIFO_DEPTH = self.MAX_DELAY
        assert(self.MAX_DELAY >= 10)


    def elaborate(self, platform):
        m = Module()
        sync = m.d.sync
        comb = m.d.comb

        # consistency: both fifo_type and fifo_data free level is the same
        # (both reads and writes simulataneously to those two)
        m.submodules.fifo_type = fifo_type = SyncFIFO(
            width=Signal(Token).width,
            depth=self.FIFO_DEPTH)

        m.submodules.fifo_data = fifo_data = SyncFIFO(
            width=32,
            depth=self.FIFO_DEPTH)

        pending      = Signal(reset=False)
        pending_data = Signal(32)
        pending_type = Signal(Token)


        is_num_state = Signal(reset=False)
        num = Signal(32, reset=0)

        # TODO queue r_rdy

        # TODO reset error each input line

        # queue should never fulfill
        # TODO test it
        sync += [
            self.err.eq(
                Mux(
                    ~fifo_data.w_rdy,
                    CalcError.Internal,
                    CalcError.Ok,
                )
            ),
            self.err.eq(Mux(
                self.err == CalcError.Ok,
                ~fifo_data.w_rdy,
                self.err
            )), # preserve error if occured once
        ]

        XD = Signal(32)
        with m.If(self.in_vld & self.in_rdy):
            # comb += XD.eq(self.in_data)
            with m.If(is_op(self.in_data) | is_parenthesis(self.in_data)):
                # TODO TODO TODO smell of bug here
                token = sig_token_type(m, sync, self.in_data)
                sync += [
                    # stop reading input for one cycle
                    # pending will be pushed in next cycle
                    self.in_rdy.eq(0),
                    pending.eq(1),
                    pending_data.eq(self.in_data),
                    pending_type.eq(token)
                ]
                with m.If(is_num_state):
                    sync += is_num_state.eq(0)
                    comb += [
                        fifo_type.w_en.eq(1),
                        fifo_type.w_data.eq(Token.NUM),

                        fifo_data.w_en.eq(1),
                        fifo_data.w_data.eq(num),
                    ]
            with m.Elif(is_white(self.in_data) & is_num_state):
                sync += is_num_state.eq(0),
                comb += [
                    fifo_type.w_en.eq(1),
                    fifo_type.w_data.eq(Token.NUM),

                    fifo_data.w_en.eq(1),
                    fifo_data.w_data.eq(num),
                ]
            with m.Elif(is_digit(self.in_data)):
                val = digit_sig_to_val(self.in_data)
                with m.If(~is_num_state):
                    sync += [
                        is_num_state.eq(1),
                        num.eq(val),
                    ]
                with m.Else():
                    sync += [
                        num.eq(num * 10 + val),
                    ]
            with m.Elif(is_newline(self.in_data)):
                whatever_data = Signal(8, reset=0xDD) # whatever
                comb += whatever_data.eq(0x11) 
                with m.If(is_num_state):
                    comb += [
                        fifo_type.w_en.eq(1),
                        fifo_data.w_en.eq(1),

                        fifo_data.w_data.eq(num),
                        fifo_type.w_data.eq(Token.NUM),
                    ]
                sync += [
                    self.in_rdy.eq(0),
                    pending.eq(1),
                    pending_data.eq(whatever_data),
                    pending_type.eq(Token.END),
                    is_num_state.eq(0), # TODO maybe handle in reset?
                ]
            with m.Else():
                sync += [
                    self.err.eq(CalcError.Lex),
                ]
        with m.Else():
            # input not read in cur cycle - got time to push pending ops to queue
            with m.If(pending):
                sync += [
                    pending.eq(0),
                    self.in_rdy.eq(1), # re-trigger reading 
                ]
                comb += [
                    fifo_type.w_en.eq(1),
                    fifo_type.w_data.eq(pending_type),

                    fifo_data.w_en.eq(1),
                    fifo_data.w_data.eq(pending_data),
                ]
        
        buf_occupied = Signal(reset=False, name="tok_buf_occupied")

        with m.If(~buf_occupied & fifo_data.r_rdy):
            comb += [
                fifo_data.r_en.eq(1),
                fifo_type.r_en.eq(1),
            ]
            sync += [
                buf_occupied.eq(1),
                self.out_data.eq(fifo_data.r_data),
                self.out_type.eq(fifo_type.r_data),
            ]

        comb += [
            self.out_vld.eq(buf_occupied),
        ]

        with m.If(self.out_rdy & self.out_vld):
            sync += [
                buf_occupied.eq(0),
            ]

        return m



def str_to_sig_array(string):
    # ord('a') = 97
    # chr(97) = 'a'
    return Array(map(lambda x: Const(ord(x), 8), string))


ERR_BYTES = {
    CalcError.Lex : str_to_sig_array("ERR LEX\n"),
    CalcError.Parse : str_to_sig_array("ERR PARSE\n"),
    CalcError.Div : str_to_sig_array("ERR DIVIDE\n"),
    CalcError.Overflow : str_to_sig_array("ERR OVERFLOW\n"),
    CalcError.Serial : str_to_sig_array("ERR SERIAL\n"),
    CalcError.Internal : str_to_sig_array("ERR INTERNAL(DEBUG)\n"),
}

DIGITS = Array( 
    [
        Const(ord(str(i)), 8) for i in range(10)
    ]
)

# def is_digit_sig(maybe_digit_sig):
#     return (maybe_digit_sig >= Const(0x30, 8)) & (Const(0x30, 8) <= Const(0x39, 8))

# def digit_to_val_sig(digit_sig):
#     return digit_sig - Const(ord('0'), 8)


class Executor(Elaboratable):
    def __init__(self):
        self.in_vld = Signal(reset=0)
        self.in_rdy = Signal(reset=0)
        self.in_data = Signal(32)
        self.in_type = Signal(Token)

        self.out_data = Signal(32)

        self.out_vld = Signal()
        self.out_rdy = Signal()

        self.err = Signal(CalcError, reset=CalcError.Ok)

        # for 32-bit width it may take at most 10 cycles for Tokenizer to assert valid_out
        # it is determined by floor $ log10(2**32) value
        self.MAX_DELAY = math.ceil(math.log10(2 ** 32))
        
        self.FIFO_DEPTH = self.MAX_DELAY
        assert(self.MAX_DELAY >= 10)

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d.sync

        aaa = Signal(32, reset=2137)
        sync += [
            # aaa.eq(0), # aaa + 1),
            aaa.eq(aaa + 1),
            self.out_vld.eq(self.in_rdy & self.in_vld)
        ]

        comb += [
            self.out_data.eq(aaa),
            self.in_rdy.eq(1),
        ]

        return m

# FIFOConnector drives 'out_rdy' and 'in_vld' signals
# class FIFOConnector(Elaboratable):
#     def __init__(self, fifo_size, fifo_shape, out_vld, out_rdy, in_vld, in_rdy):
#         self.fifo_size  = fifo_size
#         self.fifo_shape = fifo_shape
#         self.out_vld    = out_vld
#         self.out_rdy    = out_rdy
#         self.out_data   = out_data
#         self.in_rdy     = in_rdy
#         self.in_vld     = in_vld
#         self.in_data    = in_data

#         self.err = Signal(CalcError) # throws Internal when fifo overflows
    
#     def elaborate(self):
#         m = Module()
        
#         m.submodules.fifo = fifo = SyncFIFO(
#             width=self.fifo_shape,
#             depth=self.fifo_size)

#         sync += err.eq(Mux(
#             err == CalcError.Internal,
#             err, # preserve error till end of line TODO
#             ~fifo.r_rdy
#         ))

#         buf_occupied = Signal(reset=0)


#         # TODO potrzebne bedzie multple queueu
#         with m.If(~buf_occupied & fifo.r_rdy):
#             comb += [
#                 fifo_data.r_en.eq(1),
#                 fifo_type.r_en.eq(1),
#             ]
#             sync += [
#                 buf_occupied.eq(1),
#                 self.out_data.eq(fifo_data.r_data),
#                 self.out_type.eq(fifo_type.r_data),
#             ]


#         comb += self.in_vld.eq(buf_occupied)

        
        


#         return m


class Calculator(Elaboratable):
    def __init__(self, clkfreq, baudrate):
        # The frequency of the sync domain in Hz
        self.clkfreq = clkfreq
        # The requested baudrate in bps
        self.baudrate = baudrate

        self.div = int(clkfreq // baudrate)

        # From user to calculator.
        self.rxd = Signal(reset=1)
        # From calculator to user.
        self.txd = Signal()

        self.FIFO_DEPTH = 10 # TODO


    def elaborate(self, platform):
        m = Module()

        comb = m.d.comb
        sync = m.d.sync

        from uart import UartTx, UartRx # written during labs 
        # self.tx = AsyncSerialTX(divisor=self.div, data_bits=8)
        m.submodules.tx = tx = UartTx(divisor=self.div)
        m.submodules.rx = rx = UartRx(divisor=self.div)

        m.submodules.tokenizer = tokenizer = Tokenizer()

        m.submodules.fifo_rx = fifo_rx = SyncFIFO(
            width=8,
            depth=self.FIFO_DEPTH)

        buf_occupied = Signal(reset=False, name="rx_buf_occupied")
        buf_data = Signal(32, name="rx_buf_data")

        # TODO error handling!!
        # with m.If(~fifo_rx.w_rdy):
        #     sync += self.err.eq(CalcError.Internal)

        DEBUG = Signal(reset=0)
        sync += DEBUG.eq(rx.out_vld)

        lol = Signal.like(rx.out_err)
        sync += lol.eq(rx.out_err)


        comb += fifo_rx.w_en.eq(rx.out_vld & rx.out_rdy)
        comb += fifo_rx.w_data.eq(rx.out_data)

        with m.If(~buf_occupied & fifo_rx.r_rdy):
            comb += [
                fifo_rx.r_en.eq(1),
            ]
            sync += [
                buf_data.eq(fifo_rx.r_data),
                buf_occupied.eq(1),
            ]

        comb += tokenizer.in_data.eq(buf_data)
        comb += tokenizer.in_vld.eq(buf_occupied)

        with m.If(tokenizer.in_vld & tokenizer.in_rdy):
            sync += [
                buf_occupied.eq(0),
            ]

        # TODO
        comb += tokenizer.out_rdy.eq(1)

        m.submodules.exe = exe = Executor()

        m.submodules.fifo_exe_type = fifo_exe_type = SyncFIFO(
            width=Signal(Token).width,
            depth=self.FIFO_DEPTH)
        m.submodules.fifo_exe_data = fifo_exe_data = SyncFIFO(
            width=32,
            depth=self.FIFO_DEPTH)

        exe_buf_occupied = Signal(reset=False, name="exe_buf_occupied")

        with m.If(tokenizer.out_rdy & tokenizer.out_vld):
            comb += [
                fifo_exe_type.w_en.eq(1),
                fifo_exe_type.w_data.eq(tokenizer.out_type),

                fifo_exe_data.w_en.eq(1),
                fifo_exe_data.w_data.eq(tokenizer.out_data),
            ]

        with m.If(~exe_buf_occupied & fifo_exe_data.r_rdy):
            comb += [
                fifo_exe_data.r_en.eq(1),
                fifo_exe_type.r_en.eq(1),
            ]
            sync += [
                exe_buf_occupied.eq(1),
                exe.in_data.eq(fifo_exe_data.r_data),
                exe.in_type.eq(fifo_exe_type.r_data),
            ]

        comb += [
            exe.in_vld.eq(exe_buf_occupied),
        ]

        with m.If(exe.in_vld & exe.in_rdy):
            sync += [
                exe_buf_occupied.eq(0),
            ]

        tx_buf_occupied = Signal(reset=False, name="tx_buf_occupied")
        tx_buf_data = Signal(32, name="tx_buf_data")
        m.submodules.fifo_out = fifo_out = SyncFIFO(
            width=32,
            depth=100) # TODO depth


        comb += [
            exe.out_rdy.eq(1)
        ]

        with m.If(exe.out_vld & exe.out_rdy):
            comb += [
                fifo_out.w_en.eq(1),
                fifo_out.w_data.eq(exe.out_data),
            ]

        with m.If(~tx_buf_occupied & fifo_out.r_rdy):
            comb += [
                fifo_out.r_en.eq(1),
            ]
            sync += [
                tx_buf_occupied.eq(1),
                tx_buf_data.eq(fifo_out.r_data),
            ]

        digit = Signal(8)

        # 0xffffffff = 4294967295, highest possible digit obtain with dividing by 10 ** 9.
        DIVIDER_RST = Const(10 ** 9)
        divider = Signal(32, reset = DIVIDER_RST.value) 
        comb += [
            digit.eq((tx_buf_data // divider) % 10),
            tx.in_vld.eq(tx_buf_occupied),
        ]

        with m.FSM() as fsm:
            with m.State('PRE'):
                with m.If(tx_buf_occupied):
                    # digits must be sent from highest one, thus first need to find it
                    # divider != 1 for proper 0 printing
                    with m.If((divider != 1) & (digit == 0)):
                        sync += divider.eq(divider // 10)
                    with m.Else():
                        m.next = 'BUSY'
            with m.State('BUSY'):
                comb += [
                    tx.in_vld.eq(1),
                    tx.in_data.eq(DIGITS[digit]),
                ]
                with m.If(tx.in_rdy & tx.in_vld):
                    # digit sent, queue next digit or print new line
                    with m.If(divider == 1): # TODO to bez sensu
                        m.next = 'ENDLINE'
                    with m.Else():
                        sync += [
                            divider.eq(divider // 10)
                        ] 
            with m.State('ENDLINE'):
                comb += tx.in_data.eq(NEW_LINE)
                with m.If(tx.in_rdy & tx.in_vld):
                    sync += [
                        divider.eq(DIVIDER_RST.value),
                        tx_buf_occupied.eq(0),
                    ]
                    m.next = 'PRE'

        comb += [
            self.txd.eq(tx.txd),
            rx.rxd.eq(self.rxd),
            rx.out_rdy.eq(1),
        ]

        # sync += tx.in_data.eq(ERR_BYTES[CalcError.Lex][0])
        # sync += tx.in_data.eq(DIGITS[digit])
        return m


if __name__ == "__main__":
    clk_freq = 1e+6
    baud = 115200
    div = int(clk_freq // baud)
    calc = Calculator(clk_freq, baud)
    print(div)

    from nmigen.back.pysim import *
    sim = Simulator(calc)
    sim.add_clock(1e-6)

    def test_output():
        for i in range(2000):
            yield

    sim.add_sync_process(test_output)

    with sim.write_vcd('calc.vcd'):
        sim.run()