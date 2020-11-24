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
        # Bresenham help signals
        self.cur_x = Signal(self.in_x.shape())
        self.cur_y = Signal(self.in_y.shape())
        self.dst_x = Signal(self.in_x.shape())
        self.dst_y = Signal(self.in_y.shape())
        self.dx = Signal(self.in_x.shape())
        self.dy = Signal(self.in_y.shape())
        self.abs_dx = Signal(signed(width))
        self.abs_dy = Signal(signed(width))
        self.sx = Signal(signed(width))
        self.sy = Signal(signed(width))
        self.err = Signal(signed(width))

        self.cur_x_3 = Signal(self.in_x.shape())
        self.cur_y_3 = Signal(self.in_y.shape())
        self.dst_x_3 = Signal(self.in_x.shape())
        self.dst_y_3 = Signal(self.in_y.shape())
        self.dx_3 = Signal(self.in_x.shape())
        self.dy_3 = Signal(self.in_y.shape())
        self.sx_3 = Signal(signed(width))
        self.sy_3 = Signal(signed(width))
        self.err_3 = Signal(signed(width))
        self.e2 = Signal(signed(width))

        self.cur_x_last = Signal(self.in_x.shape())
        self.cur_y_last = Signal(self.in_y.shape())
        self.dst_x_last = Signal(self.in_x.shape())
        self.dst_y_last = Signal(self.in_y.shape())
        self.dx_3_last = Signal(self.in_x.shape())
        self.dy_3_last = Signal(self.in_y.shape())
        self.sx_3_last = Signal(signed(width))
        self.sy_3_last = Signal(signed(width))
        self.err_3_last = Signal(signed(width))
        self.e2_last = Signal(signed(width))

        self.in_x_2 = Signal(self.in_x.shape())
        self.in_y_2 = Signal(self.in_y.shape())
        self.in_type_2 = Signal(self.in_type.shape())

        # Forward pielining.
        # reset value is important
        self.valid_1 = Signal(reset=False)
        self.valid_2 = Signal(reset=False)
        self.valid_22 = Signal(reset=False)
        self.valid_3 = Signal(reset=False)
        self.valid_4 = Signal(reset=False)

        # enabled by sending LINE_END
        self.clock_enable = Signal(reset=True)

        # Output FIFO.
        self.out_ready = Signal()
        self.out_valid = Signal()
        self.out_type = Signal(OutPacketType)
        # Coordinates.
        self.out_x = Signal(width)
        self.out_y = Signal(width)

        self.line_end = Signal()


        # Help buf signals.
        self.buf_valid = Signal()
        self.buf_x = Signal(self.out_x.shape())
        self.buf_y = Signal(self.out_y.shape())
        self.buf_type = Signal(self.out_type.shape())
        


    def elaborate(self, platform):
        m = Module()
        sync = m.d.sync
        comb = m.d.comb

        comb += self.out_x.eq(Mux(self.buf_valid, self.buf_x, self.cur_x_3))
        comb += self.out_y.eq(Mux(self.buf_valid, self.buf_y, self.cur_y_3))
        # comb += self.out_type.eq(Mux(self.buf_valid, self.buf_type, self.type_last))
        comb += self.out_valid.eq(self.buf_valid | self.valid_3)

        comb += self.line_end.eq(self.valid_3 & ((self.cur_x_3 == self.dst_x_3) & (self.cur_y_3 == self.dst_y_3)))

        # comb += self.clock_enable.eq(self.write_done | ~self.buf_valid)
        comb += self.in_ready.eq(self.clock_enable)

        sync += self.valid_2.eq(self.in_valid & self.in_ready)
        sync += self.valid_22.eq(self.valid_2)
        sync += self.valid_3.eq(self.valid_22 & (self.in_type_2 == InPacketType.NEXT))

        sync += self.clock_enable.eq(Mux(self.valid_3, 
                                         self.line_end & self.out_ready, # line sent
                                         True))

        self.cur_x_last.eq(Mux())
        self.cur_y_last.eq(self.) 
        self.dst_x_last.eq(self.) 
        self.dst_y_last.eq(self.) 
        self.dx_3_last .eq(self.) 
        self.dy_3_last .eq(self.) 
        self.sx_3_last .eq(self.) 
        self.sy_3_last .eq(self.) 
        self.err_3_last.eq(self.) 
        self.e2_last = .eq(self.) 

        with m.If(self.clock_enable):
            # first stage handled at the very end (simply shifting input)

            with m.If(self.valid_2):
                with m.If(self.in_type_2 == InPacketType.FIRST):
                    sync += self.cur_x.eq(self.in_x_2)
                    sync += self.cur_y.eq(self.in_y_2)

                with m.Elif(self.in_type_2 == InPacketType.NEXT):
                    sync += self.dst_y.eq(self.in_y_2)
                    sync += self.dst_x.eq(self.in_x_2)
            
            with m.If(self.valid_22):
                # need cur_x and cur_y already set

                # we cannot use dst_x/dst_y yet
                sync += self.abs_dx.eq(self.cur_x - self.in_x_2)
                sync += self.abs_dy.eq(self.cur_y - self.in_y_2)
                sync += self.dx.eq(Mux(self.abs_dx[-1], -self.abs_dx, self.abs_dx))
                sync += self.dy.eq(Mux(self.abs_dy[-1], -self.abs_dy, self.abs_dy))
                sync += self.sx.eq(Mux(self.in_x_2 > self.cur_x, 1, -1))
                sync += self.sy.eq(Mux(self.in_y_2 > self.cur_y, 1, -1))
                sync += self.err.eq(self.dx - self.dy)

                    
            
            # shifting pipeline stages variables
            sync += [
                self.in_x_2.eq(self.in_x),
                self.in_y_2.eq(self.in_y),
                self.in_type_2.eq(self.in_type),

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

        # on top level - I'm setting 'clock_enable' signal
        with m.If(self.valid_3):
            # sync += self.clock_enable.eq(Mux(self.out_ready, self.line_end, False))
            with m.If(~self.out_ready):
                comb += self.valid_4.eq(False)
            with m.Elif(self.out_ready):
                # packet sent from queue or from cur_{x|y}_3
                with m.If(self.line_end):
                    comb += self.out_type.eq(OutPacketType.LINE_END)
                    comb += self.valid_4.eq(False)
                with m.Else():
                    comb += self.out_type.eq(OutPacketType.PIXEL)
                    comb += self.valid_4.eq(True)

        with m.If(self.valid_4):
            comb += self.e2.eq(self.err_3 * 2)
            with m.If(self.e2 >= -self.dy_3):
                sync += self.err_3.eq(self.err_3 - self.dy_3)
                sync += self.cur_x_3.eq(self.cur_x_3 + self.sx_3)
            with m.If(self.e2 <= self.dx_3):
                sync += self.err_3.eq(self.err_3 + self.dx_3)
                sync += self.cur_y_3.eq(self.cur_y_3 + self.sy_3)
                 
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
        print(f"e2: {e2}, dx: {dx}, dy:{dy}, sx: {sx}, sy: {sy}")
        if e2 >= -dy:
            err -= dy
            x1 += sx
        if e2 <= dx:
            err += dx
            y1 += sy

def bresenham2(x1, y1, x2, y2):
    res = []
    dx = abs(x1 - x2)
    dy = abs(y1 - y2)
    sx = 1 if x2 > x1 else -1
    sy = 1 if y2 > y1 else -1
    err = dx - dy
    while (x1, y1) != (x2, y2):
        res.append((x1, y1))
        e2 = err * 2
        print(f"e2: {e2}, dx: {dx}, dy:{dy}, sx: {sx}, sy: {sy}")
        if e2 >= -dy:
            err -= dy
            x1 += sx
        if e2 <= dx:
            err += dx
            y1 += sy
    return res


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
        for i in range(4):
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
            yield
            yield
            yield rast.in_valid.eq(1)
            yield rast.in_type.eq(in_data[0][0])
            yield rast.in_x.eq(in_data[0][1])
            yield rast.in_y.eq(in_data[0][2])
            yield
            idx = 1
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
            # print(out_data)
            # exit
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

