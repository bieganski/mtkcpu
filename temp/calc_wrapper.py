#!/usr/bin/env python3

from amaranth import *
from amaranth_boards.arty_z7 import ArtyZ720Platform
from amaranth_boards.resources import LEDResources, RGBLEDResource, ButtonResources, SwitchResources
from amaranth.build import *
from amaranth.build.run import LocalBuildProducts
from amaranth.lib.cdc import ResetSynchronizer

class PynqPlatform(ArtyZ720Platform):
    device = 'xc7z020'
    package = 'clg400'
    speed = '1'
    default_clk = "clk125"

    resources = [
        Resource("clk125", 0, Pins("H16", dir="i"), Clock(125e6), Attrs(IOSTANDARD="LVCMOS33")),
        *LEDResources(pins="R14 P14 N16 M14", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        RGBLEDResource(0, r="N15", g="G17", b="L15", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        RGBLEDResource(1, r="M15", g="L14", b="G14", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        *ButtonResources(pins="D19 D20 L20 L19", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        *SwitchResources(pins="M20 M19", attrs=Attrs(IOSTANDARD="LVCMOS33")),
    ]
    connectors = []


    def toolchain_program(self, products, name, **kwargs):
        """
        NOTE: ArtyZ720Platform already defines 'toolchain_program', though it's based on 'xc3sprog',
        but I haven't managed to make it work.
        """
        import os, subprocess
        vivado = os.environ.get("VIVADO", "vivado")
        with products.extract("{}.bit".format(name)) as bitstream_filename:
            words = [vivado, "-mode", "batch", "-source", "program.tcl", "-tclargs", bitstream_filename]
            subprocess.run(words, check=True)

class Top(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        frst = Signal(4)
        fclk = [Signal(name=f'fclk{i}') for i in range(4)]
        rst = Signal()

        m.domains.sync = ClockDomain()

        kwargs = {}
        kwargs['o_FCLKCLK'] = Cat(*fclk)
        kwargs['o_FCLKRESETN'] = frst

        m.submodules.ps = Instance('PS7', **kwargs)
        m.submodules.rst_sync = ResetSynchronizer(~frst[0], domain="sync")
        platform.add_clock_constraint(fclk[0], 50e6)

        m.d.comb += [
            ClockSignal('sync').eq(fclk[0]),
        ]

        led_g = platform.request("led")
        led_r = platform.request("led", 1)

        # FIXME some clock issue - LED does not lighten in 'sync' domain
        TODO_not_working = m.d.sync
        TODO_working = m.d.comb

        domain = TODO_working

        domain += [
            led_r.eq(1),
            led_g.eq(1),
        ]

        return m
    
plat = PynqPlatform()
plat.build(Top(), do_program=True)

# don't rebuild, only program
# plat.toolchain_program(products=LocalBuildProducts(root="./build"), name="top")