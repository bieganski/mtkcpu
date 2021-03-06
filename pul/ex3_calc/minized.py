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
        Resource("vga_r", 0, Pins("L15 M15 L14 M14", dir='o'), Attrs(IOSTANDARD="LVCMOS33", DRIVE='2')),
        Resource("vga_b", 0, Pins("K13 L13 N13 N14", dir='o'), Attrs(IOSTANDARD="LVCMOS33", DRIVE='2')),
        # Resource("vga_g", 0, Pins("P15 R15 R12 R13", dir='o'), Attrs(IOSTANDARD="LVCMOS33", DRIVE='2')),
        Resource("vga_g", 0, Pins("P13 P14 N11 N12", dir='o'), Attrs(IOSTANDARD="LVCMOS33", DRIVE='2')),
        Resource("vga_hsync", 0, Pins("P15", dir='o'), Attrs(IOSTANDARD="LVCMOS33", DRIVE='2')),
        Resource("vga_vsync", 0, Pins("R15", dir='o'), Attrs(IOSTANDARD="LVCMOS33", DRIVE='2')),
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


class TopWrapper(Elaboratable):
    def __init__(self, mod):
        self.mod = mod

    def elaborate(self, platform):
        m = Module()

        frst = Signal(4)
        fclk = [Signal(name=f"fclk{i}") for i in range(4)]

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
        m.submodules.rst_sync = ResetSynchronizer(~frst[0], domain='sync')

        platform.add_clock_constraint(fclk[0], 50e6)

        m.submodules.mod = self.mod

        m.d.comb += [
            ClockSignal('sync').eq(fclk[0]),
        ]

        m.d.comb += ResetSignal("sync").eq(~Signal(reset=False))

        return m


class Top(Elaboratable):
    def elaborate(self, platform):

        from calc import Calculator
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
        # m.submodules.rst_sync = rst_sync = ResetSynchronizer(~frst[0], domain='sync')
        platform.add_clock_constraint(fclk[0], 50e6)

        # m.submodules.blinky = blinky = Blinky()
        # m.submodules.calc = calc = Calculator(50000000, 115200)
        m.domains.aaa = ClockDomain()
        

        led0 = platform.request("led", 0)
        led1 = platform.request("led", 1)
       
        ctr0 = Signal(26, reset=-1) 
        ctr1 = Signal(26, reset=-1) # czerwona miga szybciej

        clk_slow = Signal()
        locked = Signal()
        # pll = m.submodules.pll = Instance("PLLE2_BASE",
        # pll = m.submodules.pll = Instance("PLLE2_ADV",
        #     i_CLKIN1 = fclk[0],
        #     i_CLKFBIN = clk_slow,
        #     # i_CLKFBOUT = clk_slow,
        #     i_RST = Const(1, 1),
        #     o_CLKOUT0 = clk_slow,
        #     o_LOCKED = locked,
        #     p_CLKFBOUT_MULT=16,
        #     p_DIVCLK_DIVIDE=1, # 1 is default
        #     # AND! 1000 mul * / (20ns * divdiv) <- [800, 1600]
        #     p_CLKOUT0_DIVIDE=8, # TODO should be the same as fclk1
        #     # p_COMPENSATION="INTERNAL",
        #     # p_COMPENSATION="EXTERNAL",
        #     p_COMPENSATION="BUF_IN",
        # )

        mmcm_fb = Signal() 
        mmcm = m.submodules.mmcm = Instance("MMCME2_ADV",
            i_CLKIN1 = fclk[0],
            i_CLKFBIN = mmcm_fb,
            o_CLKFBOUT = mmcm_fb,
            o_CLKOUT1 = clk_slow,
            o_LOCKED = locked,
            p_CLKIN1_PERIOD = 20, # 50 mhz = 20 ns
            p_CLKOUT1_DIVIDE = 50, # 18 * , # TODO
            p_DIVCLK_DIVIDE = 2, # TODO
            p_CLKFBOUT_MULT_F = 25,
            p_COMPENSATION="INTERNAL",
            # p_COMPENSATION="EXTERNAL",
            # p_COMPENSATION="BUF_IN",
        )

        m.d.comb += [
            ClockSignal('sync').eq(clk_slow),
            # ClockSignal('sync').eq(fclk[1]),
            ClockSignal('aaa').eq(clk_slow),
        ]

        m.d.comb += ResetSignal("aaa").eq(~locked)
        m.d.comb += ResetSignal("sync").eq(~locked)
        
        m.d.sync += ctr0.eq(ctr0 + 1)
        m.d.aaa += ctr1.eq(ctr1 + 1)
        
        m.d.comb += [
            led1.o.eq(ctr0[25]),
            led0.o.eq(ctr1[25]),
        ]


        ######## VGA

        hsync = platform.request('vga_hsync', 0)
        vsync = platform.request('vga_vsync', 0)
        r = platform.request('vga_r', 0)
        g = platform.request('vga_g', 0)
        b = platform.request('vga_b', 0)

        ####

        # m.d.comb += [
        #     r.eq(clk_slow),
        #     g.eq(1),
        #     b.eq(7),
        #     hsync.eq(clk_slow),
        #     vsync.eq(1),
        # ]

        # return m

        ####

        vctr = Signal(10)
        hctr = Signal(10)

        with m.If(hctr == 800 - 1):
            m.d.sync += [
                hctr.eq(0),
            ]
            with m.If(vctr == 525 - 1):
                m.d.sync += [
                    vctr.eq(0),
                ]
            with m.Else():
                m.d.sync += [
                    vctr.eq(vctr + 1),
                ]
        with m.Else():
            m.d.sync += [
                hctr.eq(hctr + 1),
            ]

        active = Signal()
        dist2 = Signal(22)
        m.d.comb += [
            active.eq((hctr < 640) & (vctr < 480)),
            dist2.eq((hctr - 320).as_signed() * (hctr - 320).as_signed() + (vctr - 240).as_signed() * (vctr - 240).as_signed()),
        ]
        m.d.sync += [
            hsync.o.eq((hctr >= 640 + 16) & (hctr < 640 + 16 + 96)),
            vsync.o.eq((vctr >= 480 + 10) & (vctr < 480 + 10 + 2)),
            r.o.eq(Mux(active, Mux(dist2 < 200 * 200, 15, 0), 0)), # 7
            g.o.eq(Mux(active, Mux(dist2 < 160 * 160, 15, 0), 0)), # 7
            b.o.eq(Mux(active, Mux(dist2 < 120 * 120, 15, 0), 0)), # 3
        ]

        return m
    


# MinizedPlatform().build(Blinky(), do_program=True)
if __name__ == "__main__":
    MinizedPlatform().build(Top(), do_program=True)
