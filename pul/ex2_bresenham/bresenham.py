#!/usr/bin/env python3

from enum import Enum
import random
from nmigen import *
from nmigen.cli import main, pysim
from nmigen.lib.fifo import SyncFIFO

class InPacketType(Enum):
    FIRST = 0
    NEXT = 1


class OutPacketType(Enum):
    PIXEL = 0
    LINE_END = 1


class LineRasterizer(Elaboratable):
    # `width` is the coordinates' width in bits.
    def __init__(self, width):
        self.width = width

        # Input FIFO.
        self.in_ready = Signal()
        self.in_valid = Signal()
        self.in_type = Signal(InPacketType)
        # Coordinates.
        self.in_x = Signal(width)
        self.in_y = Signal(width)

        
        # Internals.
        self.FIFO_DEPTH = 10
        self.fifo = SyncFIFO(width=2*width, depth=self.FIFO_DEPTH)

        self.input_consumed = Signal()
        self.fifo_output_consumed = Signal()
        self.ready_to_dispatch = Signal()
        self.out_fifo = Signal(2 * width)

        self.in_x_consumed = Signal(width)
        self.in_y_consumed = Signal(width)
        self.in_type_consumed = Signal(InPacketType)

        self.out_x_from_fifo = Signal(width)
        self.out_y_from_fifo = Signal(width)
        self.out_type_from_fifo = Signal(InPacketType)
        
        # Bresenham help signals
        self.cur_x = Signal(width)
        self.cur_y = Signal(width)
        self.dst_x = Signal(width)
        self.dst_y = Signal(width)
        self.dx = Signal(width)
        self.dy = Signal(width)
        self.abs_dx = Signal(signed(width))
        self.abs_dy = Signal(signed(width))
        self.sx = Signal(signed(width))
        self.sy = Signal(signed(width))
        self.err = Signal(signed(width))
        self.e2 = Signal(signed(width))

        # forward pielining
        self.valid_2 = Signal()
        self.valid_3 = Signal()
        self.valid_4 = Signal()
        self.valid_5 = Signal()

        # stall detection (backward pipelining)
        # self.bubble1 = Signal()
        # self.bubble2 = Signal()
        # self.bubble3 = Signal()
        # self.bubble4 = Signal()

        self.buf_valid = Signal()
        self.buf_x = Signal(out_x.shape())
        self.buf_y = Signal(out_y.shape())
        self.buf_type = Signal(out_type.shape())

        self.valid1 = Signal()
        self.valid_last = Signal()

        # indicates whether last module (while loop, non-deterministic execution time)
        # is ready to get new data
        self.ready_last = Signal()

        self.line_end = Signal()
        self.packet_sent = Signal()

        
        # Output FIFO.
        self.out_ready = Signal()
        self.out_valid = Signal()
        self.out_type = Signal(OutPacketType)
        # Coordinates.
        self.out_x = Signal(width)
        self.out_y = Signal(width)


    def elaborate(self, platform):
        m = Module()
        m.submodules += self.fifo
        sync = m.d.sync
        comb = m.d.comb

        comb += self.out_x.eq(Mux(buf_valid, buf_x, last_x))
        comb += self.out_y.eq(Mux(buf_valid, buf_y, last_y))
        comb += self.out_type.eq(Mux(buf_valid, buf_type, last_type))
        comb += self.out_valid.eq(buf_valid | valid_last)
        
        comb += self.valid_last.eq(self.valid_3) # TODO

        with m.If(self.valid_4):
            comb += self.e2.eq(self.err + self.err)
            with m.If(self.e2 >= -self.dy_3):
                sync += self.err_3.eq(self.err_3 - self.dy_3)
                sync += self.cur_x_3.eq(self.cur_x_3 + self.sx_3)
            with m.Elif(self.e2 <= self.dx):
                sync += self.err_3.eq(self.err_3 + self.dx_3)
                sync += self.cur_y_3.eq(self.cur_y_3 + self.sy_3)

        # if data has been sent, we can inform stage 3 about it
        comb += self.packet_sent.eq(Mux(self.out_ready & self.out_valid, True, False))
        comb += self.line_end_sent.eq(self.packet_sent & Mux(self.buf_valid,
                                                            self.out_type == OutPacketType.LINE_END,
                                                            self.last_type == OutPacketType.LINE_END))

        comb += self.line_end.eq(Mux((self.cur_x_3 == self.dst_x_3) & (self.cur_y_3 == self.dst_y_3), True, False))

        with m.If(self.valid_3 & ~self.out_ready):
            with m.If((self.line_end):
                sync += buf_type.eq(OutPacketType.LINE_END)
                sync += buf_valid.eq(True)    
            with m.Else():
                sync += buf_x.eq(self.cur_x_3)
                sync += buf_y.eq(self.cur_y_3)
                sync += buf_type.eq(self.OutPacketType.PIXEL)
                sync += buf_valid.eq(True)


        # TODO
        self.start = Signal()
        comb += self.start.eq(Mux(~self.buf_valid | ~self.ready_last,
                                 True,
                                False))
        with m.If(~self.start):
            # cannot consume input
            m.d.comb += in_ready.eq(0)
        with m.Else(): # ~self.buf_valid | ~self.ready_last
            # stage 1 - consuming input
            # there is some place for new data, we can read
            # TODO info about shifting pipeline
            comb += self.in_ready.eq(True)
            sync += self.valid_2.eq(True)

            # stage 2 - calculating 'err'
            with m.If(self.valid_2):
                with m.If(self.in_type2 == InPacketType.FIRST):
                    sync += self.cur_x.eq(self.in_x_2)
                    sync += self.cur_y.eq(self.in_y_2)

                    sync += self.valid_3.eq(False)
                with m.Elif(self.in_type2 == InPacketType.NEXT):
                    sync += self.dst_x.eq(self.in_x_2)
                    sync += self.dst_y.eq(self.in_y_2)
                    
                    comb += self.abs_dx.eq(self.cur_x - self.dst_x)
                    comb += self.abs_dy.eq(self.cur_y - self.dst_y)
                    comb += self.dx.eq(Mux(self.abs_dx[-1], -self.abs_dx, self.abs_dx))
                    comb += self.dy.eq(Mux(self.abs_dy[-1], -self.abs_dy, self.abs_dy))
                    comb += self.sx.eq(Mux(self.dst_x > self.cur_x, 1, -1))
                    comb += self.sy.eq(Mux(self.dst_y > self.cur_y, 1, -1))
                    comb += self.err.eq(self.dx - self.dy)
            
                    sync += self.valid_3.eq(True)

            # shifting pipeline stages variables
            sync += [
                self.valid_2.eq(self.valid_buf),
                self.valid_3.eq(self.valid_2),
                self.valid_4.eq(self.valid_3),
                self.valid_5.eq(self.valid_4),

                self.in_x_1.eq(self.in_x),
                self.in_y_1.eq(self.in_y),
                self.in_type_1.eq(self.in_type),

                self.err_3.eq(self.err),
                self.cur_x_3.eq(self.cur_x),
                self.cur_y_3.eq(self.cur_y),
                self.dst_x_3.eq(self.dst_x),
                self.dst_y_3.eq(self.dst_y),
                self.dx_3.eq(self.dx),
                self.dy_3.eq(self.dy),
                self.sx_3.eq(self.sx),
                self.sy_3.eq(self.sy),

            ]
        return m


def bresenham(x1, y1, x2, y2):
    dx = abs(x1 - x2)
    dy = abs(y1 - y2)
    sx = 1 if x2 > x1 else -1
    sy = 1 if y2 > y1 else -1
    err = dx - dy
    while (x1, y1) != (x2, y2):
        yield x1, y1
        e2 = err * 2
        if e2 >= -dy:
            err -= dy
            x1 += sx
        if e2 <= dx:
            err += dx
            y1 += sy


if __name__ == '__main__':
    rast = LineRasterizer(8)
    ports = [
        rast.in_ready, rast.in_valid, rast.in_type, rast.in_x, rast.in_y,
        rast.out_ready, rast.out_valid, rast.out_type, rast.out_x, rast.out_y,
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

        sim = Simulator(rast)
        sim.add_clock(1e-6)

        in_data = []
        out_data = []
        for i in range(2):
            x = 4 * i + 2 # random.randrange(1 << rast.width)
            y = 2 * i**2  # random.randrange(1 << rast.width)
            if i == 0 or random.randrange(8) == 0:
                t = InPacketType.FIRST
            else:
                t = InPacketType.NEXT
                for ox, oy in bresenham(lx, ly, x, y):
                    out_data.append((ox, oy))
                out_data.append(OutPacketType.LINE_END)
            in_data.append((t, x, y))
            lx = x
            ly = y

        
        def print_input(input):
            try:
                t, x, y = input
            except:
                x, y = input
                t = ""
            print(f'INPUT {t}: <{x},{y}>')

        def print_line(prev, act):
            out_data = []
            _, px, py = prev
            _, ax, ay = act
            for ox, oy in bresenham(px, py, ax, ay):
                    out_data.append((ox, oy))


            print_input(prev)
            for pair in out_data:
                print_input(pair)
            print_input(act)

        
        def feed_input():
            for pair in zip(in_data, in_data[1:]):
                    print_line(*pair)
            yield
            idx = 0
            while idx < len(in_data):
                if random.randrange(8) == 0:
                    yield rast.in_valid.eq(0)
                    yield
                else:
                    yield rast.in_valid.eq(1)
                    yield rast.in_type.eq(in_data[idx][0])
                    yield rast.in_x.eq(in_data[idx][1])
                    yield rast.in_y.eq(in_data[idx][2])
                    yield
                    if (yield rast.in_ready):
                        idx += 1

        def test_output():
            fail = False
            yield
            yield Settle()
            idx = 0
            while idx < len(out_data):
                if random.randrange(8) == 0:
                    yield rast.out_ready.eq(0)
                    yield
                else:
                    yield rast.out_ready.eq(1)
                    yield
                    if (yield rast.out_valid):
                        ot = OutPacketType((yield rast.out_type))
                        ox = yield rast.out_x
                        oy = yield rast.out_y
                        if out_data[idx] == OutPacketType.LINE_END:
                            if ot != OutPacketType.LINE_END:
                                print(f'FAIL {idx} — expected LINE_END, got PIXEL {ox} {oy}')
                                fail = True
                        else:
                            ex, ey = out_data[idx]
                            if ot != OutPacketType.PIXEL:
                                print(f'FAIL {idx} — expected PIXEL {ex} {ey}, got LINE_END')
                                fail = True
                            elif (ex, ey) != (ox, oy):
                                print(f'FAIL {idx} — expected PIXEL {ex} {ey}, got PIXEL {ox} {oy}')
                                fail = True
                        idx += 1
            if not fail:
                print('PASS')

        sim.add_sync_process(test_output)
        sim.add_sync_process(feed_input)

        with sim.write_vcd('bresenham.vcd'):
            sim.run()

    if args.action == "rtlil":
        from nmigen.back import rtlil

        print(rtlil.convert(rast, ports=ports))

    if args.action == "verilog":
        from nmigen.back import verilog

        print(verilog.convert(rast, ports=ports))

