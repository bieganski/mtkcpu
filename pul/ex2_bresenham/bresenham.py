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
        
        # Internals (help signals)
        self.abs_dx_3 = Signal(signed(width + 2))
        self.abs_dy_3 = Signal(signed(width + 2))

        self.cur_x_3 = Signal(self.in_x.shape())
        self.cur_y_3 = Signal(self.in_y.shape())
        self.dst_x_3 = Signal(self.in_x.shape())
        self.dst_y_3 = Signal(self.in_y.shape())
        self.dx_3 = Signal(width)
        self.dy_3 = Signal(width)
        self.sx_3 = Signal(signed(2))
        self.sy_3 = Signal(signed(2))
        self.err_3 = Signal(signed(width + 2))
        self.e2 = Signal(signed(width + 3))

        self.cur_x_4 = Signal(self.in_x.shape())
        self.cur_y_4 = Signal(self.in_y.shape())
        self.dst_x_4 = Signal(self.in_x.shape())
        self.dst_y_4 = Signal(self.in_y.shape())
        self.dx_4 = Signal(width)
        self.dy_4 = Signal(width)
        self.sx_4 = Signal(signed(2))
        self.sy_4 = Signal(signed(2))
        self.err_4 = Signal(signed(width + 3))

        self.in_x_2 = Signal(self.in_x.shape())
        self.in_y_2 = Signal(self.in_y.shape())
        self.in_type_2 = Signal(InPacketType)

        self.in_x_3 = Signal(self.in_x.shape())
        self.in_y_3 = Signal(self.in_y.shape())
        self.in_type_3 = Signal(InPacketType)

        # Forward pielining.
        # reset value is important
        self.valid_1 = Signal(reset=False)
        self.valid_2 = Signal(reset=False)
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

        self.pos_reset = Signal(reset=True)

        self.DEBUG_CTR = Signal(range(1000), reset=1)


        # Help buf signals.
        self.buf_valid = Signal()
        self.buf_x = Signal(self.out_x.shape())
        self.buf_y = Signal(self.out_y.shape())
        self.buf_type = Signal(self.out_type.shape())
        


    def elaborate(self, platform):
        m = Module()
        sync = m.d.sync
        comb = m.d.comb

        comb += [
            self.in_ready.eq(self.clock_enable)
        ]

        with m.If(self.clock_enable):
            
            # those rules are important (pipeline constraints)
            sync += [
                self.valid_2.eq(self.in_ready & self.in_valid),
                self.valid_3.eq(self.valid_2 & self.in_type_2 == InPacketType.NEXT),
                self.valid_4.eq(self.valid_3),
            ]

            sync += [
                self.in_x_2.eq(self.in_x),
                self.in_y_2.eq(self.in_y),
                self.in_type_2.eq(self.in_type),

                self.in_x_3.eq(self.in_x_2),
                self.in_y_3.eq(self.in_y_2),
                self.in_type_3.eq(self.in_type_2),

                # cur_{x/y}_4 set below conditionally
                self.dst_x_4.eq(self.dst_x_3),
                self.dst_y_4.eq(self.dst_y_3),
                self.dx_4.eq(self.dx_3),
                self.dy_4.eq(self.dy_3),
                self.sx_4.eq(self.sx_3),
                self.sy_4.eq(self.sy_3),
                self.err_4.eq(self.err_3),
            ]

            with m.If(self.in_ready):
                pass # packet read, do nothing

            with m.If(self.valid_2):
                with m.If(self.in_type_2 == InPacketType.FIRST):
                    sync += self.cur_x_3.eq(self.in_x_2)
                    sync += self.cur_y_3.eq(self.in_y_2)
                    sync += self.pos_reset.eq(True)

                with m.Elif(self.in_type_2 == InPacketType.NEXT):
                    sync += self.dst_y_3.eq(self.in_y_2)
                    sync += self.dst_x_3.eq(self.in_x_2)
            
            with m.If(self.valid_3):
                cur_x = Signal(self.cur_x_3.shape())
                cur_y = Signal(self.cur_y_3.shape())
                comb += cur_x.eq(Mux(
                    self.pos_reset, 
                    self.cur_x_3,
                    self.cur_x_4,
                ))
                comb += cur_y.eq(Mux(
                    self.pos_reset, 
                    self.cur_y_3,
                    self.cur_y_4,
                ))

                comb += self.abs_dx_3.eq(cur_x - self.in_x_3)
                comb += self.abs_dy_3.eq(cur_y - self.in_y_3)
                comb += self.dx_3.eq(Mux(self.abs_dx_3[-1], -self.abs_dx_3, self.abs_dx_3))
                comb += self.dy_3.eq(Mux(self.abs_dy_3[-1], -self.abs_dy_3, self.abs_dy_3))
                comb += self.sx_3.eq(Mux(self.in_x_3 > cur_x, 1, -1))
                comb += self.sy_3.eq(Mux(self.in_y_3 > cur_y, 1, -1))
                comb += self.err_3.eq(self.dx_3 - self.dy_3)

                with m.If(self.pos_reset):
                    sync += [
                        self.cur_x_4.eq(self.cur_x_3),
                        self.cur_y_4.eq(self.cur_y_3),

                        # ugly hack, prevents from sequence [first, next, first]
                        # self.pos_reset.eq(False)
                        self.pos_reset.eq((self.valid_2 & (self.in_type_2 == InPacketType.FIRST)))
                    ]

        # out of global clock_enable
        with m.If(self.valid_4):
            comb += self.line_end.eq((self.cur_x_4 == self.dst_x_4) & (self.cur_y_4 == self.dst_y_4))

            comb += self.out_valid.eq(True)
            comb += self.clock_enable.eq(self.out_ready & self.line_end)

            with m.If(self.out_ready):
                sync += self.DEBUG_CTR.eq(self.DEBUG_CTR + 1)

            with m.If(self.out_ready & ~self.line_end):
                comb += self.e2.eq(self.err_4 * 2)
                with m.If((self.e2 >= -self.dy_4) & (self.e2 <= self.dx_4)):
                    # FIXME can we better (branch redundancy)?
                    sync += self.err_4.eq(self.err_4 - self.dy_4 + self.dx_4)
                    sync += self.cur_x_4.eq(self.cur_x_4 + self.sx_4)
                    sync += self.cur_y_4.eq(self.cur_y_4 + self.sy_4)

                with m.Elif(self.e2 >= -self.dy_4):
                    sync += self.err_4.eq(self.err_4 - self.dy_4)
                    sync += self.cur_x_4.eq(self.cur_x_4 + self.sx_4)
                    
                with m.Elif(self.e2 <= self.dx_4):
                    sync += self.err_4.eq(self.err_4 + self.dx_4)
                    sync += self.cur_y_4.eq(self.cur_y_4 + self.sy_4)

                
        comb += self.out_x.eq(self.cur_x_4)
        comb += self.out_y.eq(self.cur_y_4)
        comb += self.out_type.eq(Mux(
                                    self.line_end,
                                    OutPacketType.LINE_END,
                                    OutPacketType.PIXEL,
                                    ))
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
        for i in range(256):
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

