#!/usr/bin/python3

from nmigen.vendor.xilinx_7series import  *
from nmigen.build import *
from nmigen_boards.resources import *
class MinizedPlatform(Xilinx7SeriesPlatform):
    device = 'xc7z007s'
    package = 'clg225'
    default_clk = "clk125"
    speed = '1'

# Bank 35
# Note that the LEDs and switch are shared with ARDUINO_A[3:5]. Therefore
# these next three pin locations get repeated. Depending on which features
# you use, one or the other constraints should be commented out.
# set_property PACKAGE_PIN E13 [get_ports {PL_LED_G       }];  # "E13.ARDUINO_A3"
# set_property PACKAGE_PIN E12 [get_ports {PL_LED_R       }];  # "E12.ARDUINO_A4"
# set_property PACKAGE_PIN E11 [get_ports {PL_SW          }];  # "E11.ARDUINO_A5"

    resources = [
        Resource("clk125", 0, Pins("H16", dir="i"), Clock(125e6), Attrs(IOSTANDARD="LVCMOS33")),
        *LEDResources(pins="E13 E12", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        *SwitchResources(pins="E11", attrs=Attrs(IOSTANDARD="LVCMOS33")),
    ]
    speed = '1'
    # [
    #     Resource("clk125", 0, Pins("H16", dir="i"), Clock(125e6), Attrs(IOSTANDARD="LVCMOS33")),
    #     *LEDResources(pins="R14 P14 N16 M14", attrs=Attrs(IOSTANDARD="LVCMOS33")),
    #     RGBLEDResource(0, r="N15", g="G17", b="L15", attrs=Attrs(IOSTANDARD="LVCMOS33")),
    #     RGBLEDResource(1, r="M15", g="L14", b="G14", attrs=Attrs(IOSTANDARD="LVCMOS33")),
    #     *ButtonResources(pins="D19 D20 L20 L19", attrs=Attrs(IOSTANDARD="LVCMOS33")),
    #     *SwitchResources(pins="M20 M19", attrs=Attrs(IOSTANDARD="LVCMOS33")),
    # ]
    connectors = []

from nmigen_boards import arty_z7
from nmigen_boards.arty_z7 import ArtyZ720Platform # arty_z7

from nmigen_boards.test.blinky import *
from nmigen import *
from nmigen.lib.cdc import ResetSynchronizer

class Top(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        frst = Signal(4) # TODO dlaczego 4
        fclk = [Signal(name=f"fclk{i}") for i in range(4)]
        rst = Signal()

        m.domains.sync = ClockDomain()

        kwargs = {}
        kwargs['o_FCLKCLK'] = Cat(*fclk)
        kwargs['o_FCLKRESETN'] = frst
        # TODO rest of kwargs

        m.submodules.ps = Instance('PS7', **kwargs)
        m.submodules.rst_sync = rst_sync = ResetSynchronizer(~frst[0], domain='sync')
        platform.add_clock_constraint(fclk[0], 50e6)

        m.submodules.blinky = blinky = Blinky()

        m.d.comb += [
            ClockSignal('sync').eq(fclk[0]),
        ]

        return m


# MinizedPlatform().build(Blinky(), do_program=True)
MinizedPlatform().build(Top(), do_program=False)
