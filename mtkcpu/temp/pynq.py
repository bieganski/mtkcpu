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
        from pathlib import Path
        vivado = os.environ.get("VIVADO", "vivado")
        program_tcl = Path(__file__).parent / "program.tcl"
        with products.extract("{}.bit".format(name)) as bitstream_filename:
            words = [vivado, "-mode", "batch", "-source", str(program_tcl.absolute()), "-tclargs", bitstream_filename]
            subprocess.run(words, check=True)

class Top(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        # m.submodules.ps = Instance('PS7')
        # platform.add_clock_constraint(ClockSignal("sync"), 125)

        led0 = platform.request("led", 0)
        led1 = platform.request("led", 1)

        ctr = Signal(25)
        m.d.sync += ctr.eq(ctr + 1)

        with m.If(ctr == 0):
            for led in [led0, led1]:
                m.d.sync += led.o.eq(~led.o)

        return m


if __name__ == "__main__":
    from amaranth.back import verilog
    top = Top()
    with open("top.v", "w") as f:
        f.write(verilog.convert(top, platform=PynqPlatform(), ports=[]))

    # build and load ...
    plat = PynqPlatform()
    plat.build(Top(), do_program=True)

    # ... or only load.
    # plat.toolchain_program(products=LocalBuildProducts(root="./build"), name="top")

