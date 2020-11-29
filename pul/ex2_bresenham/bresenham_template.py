#!/usr/bin/env python3
from enum import Enum
import random
from nmigen import *
from nmigen.cli import main, pysim

from HAHA import LineRasterizer

class InPacketType(Enum):
    FIRST = 0
    NEXT = 1


class OutPacketType(Enum):
    PIXEL = 0
    LINE_END = 1

'''
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

        # Output FIFO.
        self.out_ready = Signal()
        self.out_valid = Signal()
        self.out_type = Signal(OutPacketType)
        # Coordinates.
        self.out_x = Signal(width)
        self.out_y = Signal(width)

    def elaborate(self, platform):
        m = Module()

        # FILL ME

        return m
'''

show_first_n = 150
def bresenham(x1, y1, x2, y2):
    dx = abs(x1 - x2)
    dy = abs(y1 - y2)
    sx = 1 if x2 > x1 else -1
    sy = 1 if y2 > y1 else -1
    err = dx - dy
    global show_first_n 
    while (x1, y1) != (x2, y2):
        yield x1, y1
        e2 = err * 2
        if show_first_n > 0:
            show_first_n -= 1
            print(f"e2: {e2}, dx: {dx}, dy:{dy}, sx: {sx}, sy: {sy} CUR(x,y) = =({x1}, {y1})")
        if e2 >= -dy:
            err -= dy
            x1 += sx
        if e2 <= dx:
            err += dx
            y1 += sy


if __name__ == '__main__':
    rast = LineRasterizer(6)
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
        for i in range(7):
            x = random.randrange(1 << rast.width)
            y = random.randrange(1 << rast.width)
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

        def feed_input():
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
                        print("got (", ot, ox, oy, ")", "expected", out_data[idx] )
                        if out_data[idx] == OutPacketType.LINE_END:
                            if ot != OutPacketType.LINE_END:
                                print(f'FAIL {idx} — expected LINE_END, got PIXEL {ox} {oy}')
                                fail = True
                                # return
                        else:
                            ex, ey = out_data[idx]
                            if ot != OutPacketType.PIXEL:
                                print(f'FAIL {idx} — expected PIXEL {ex} {ey}, got LINE_END')
                                fail = True
                                # return
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

