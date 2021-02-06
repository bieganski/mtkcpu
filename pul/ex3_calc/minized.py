#!/usr/bin/python3

from nmigen.vendor.xilinx_7series import  *
from nmigen.build import *
from nmigen_boards.resources import *
import pickle
class MinizedPlatform(Xilinx7SeriesPlatform):
    device = 'xc7z007s'
    package = 'clg225'
    # default_clk = "clk125"
    default_clk = "fclk0"
    speed = '1'

    resources = [
        # Resource("clk125", 0, Pins("H16", dir="i"), Clock(125e6), Attrs(IOSTANDARD="LVCMOS33")),
        *LEDResources(pins="E13 E12", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        *SwitchResources(pins="E11", attrs=Attrs(IOSTANDARD="LVCMOS33")),
    ]

    connectors = []

    def toolchain_program(self, products, name, **kwargs):
        import subprocess
        import os
        import beepy
        bit_fname = f"build/{name}.bit"
        program_script = os.path.expanduser("~/program.sh")
        subprocess.run([program_script, bit_fname, "todo.bit"])
        beepy.beep()
        # print(products)
        # print(name)
        # pickle.dump( products, open( "products.out", "wb" ) )


from nmigen_boards.test.blinky import *
from nmigen import *
from nmigen.lib.cdc import ResetSynchronizer

from calc import *

class Top(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        frst = Signal(4)
        fclk = [Signal(name=f"fclk{i}") for i in range(4)]
        rst = Signal()

        m.domains.sync = ClockDomain()

        kwargs = {}
        kwargs['o_FCLKCLK'] = Cat(*fclk)
        kwargs['o_FCLKRESETN'] = frst


        rx = Signal()
        tx = Signal()

        kwargs['i_EMIOUART1RX'] = rx
        kwargs['o_EMIOUART1TX'] = tx

        for i in range(2):
            kwargs[f'i_EMIOUART{i}CTSN'] = C(1, 1)
            kwargs[f'i_EMIOUART{i}DCDN'] = C(1, 1)
            kwargs[f'i_EMIOUART{i}DSRN'] = C(1, 1)
            kwargs[f'i_EMIOUART{i}RIN'] = C(1, 1)
            kwargs[f'i_EMIOUART{i}RX'] = C(1, 1)
        # TODO rest of kwargs

        m.submodules.ps = Instance('PS7', **kwargs)
        m.submodules.rst_sync = rst_sync = ResetSynchronizer(~frst[0], domain='sync')
        platform.add_clock_constraint(fclk[0], 100e6)

        # m.submodules.blinky = blinky = Blinky()
        # m.submodules.calc = calc = Calculator(50000000, 115200)
        m.domains.aaa = ClockDomain()
        led0 = platform.request("led", 0)
        led1 = platform.request("led", 1)
       
        ctr0 = Signal(26, reset=-1)
        ctr1 = Signal(26, reset=-1)
        
        m.d.sync += ctr0.eq(ctr0 + 1)
        m.d.aaa += ctr1.eq(ctr1 + 1)
        
        m.d.comb += [
            led0.o.eq(ctr0[25]),
            led1.o.eq(ctr1[25]),
        ]
        
        m.d.comb += [
            ClockSignal('sync').eq(fclk[1]),
            ClockSignal('aaa').eq(fclk[0]),
          #   rx.eq(calc.txd),
          #   calc.rxd.eq(tx),
        ]

        return m
    


# MinizedPlatform().build(Blinky(), do_program=True)
MinizedPlatform().build(Top(), do_program=True)
