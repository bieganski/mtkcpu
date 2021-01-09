#!/usr/bin/env python3

from nmigen import *
from nmigen.vendor.xilinx_7series import *
from nmigen_boards.resources import *
from nmigen.build import *
from nmigen.lib.cdc import ResetSynchronizer

from calc import Calculator


class PynqPlatform(Xilinx7SeriesPlatform):
    device = 'xc7z020'
    package = 'clg400'
    speed = '1'
    resources = [
        Resource("clk125", 0, Pins("H16", dir="i"), Clock(125e6), Attrs(IOSTANDARD="LVCMOS33")),
        *LEDResources(pins="R14 P14 N16 M14", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        RGBLEDResource(0, r="N15", g="G17", b="L15", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        RGBLEDResource(1, r="M15", g="L14", b="G14", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        *ButtonResources(pins="D19 D20 L20 L19", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        *SwitchResources(pins="M20 M19", attrs=Attrs(IOSTANDARD="LVCMOS33")),
    ]
    connectors = []

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

        # AXI
        for i in range(2):
            kwargs[f'i_MAXIGP{i}ACLK'] = fclk[0]

            kwargs[f'i_MAXIGP{i}ARREADY'] = C(0, 1)

            kwargs[f'i_MAXIGP{i}AWREADY'] = C(0, 1)

            kwargs[f'i_MAXIGP{i}WREADY'] = C(0, 1)

            kwargs[f'i_MAXIGP{i}BVALID'] = C(0, 1)
            kwargs[f'i_MAXIGP{i}BID'] = C(0, 12)
            kwargs[f'i_MAXIGP{i}BRESP'] = C(0, 2)

            kwargs[f'i_MAXIGP{i}RVALID'] = C(0, 1)
            kwargs[f'i_MAXIGP{i}RLAST'] = C(0, 1)
            kwargs[f'i_MAXIGP{i}RID'] = C(0, 12)
            kwargs[f'i_MAXIGP{i}RRESP'] = C(0, 2)
            kwargs[f'i_MAXIGP{i}RDATA'] = C(0, 32)

        for nm in ['SAXIGP0', 'SAXIGP1', 'SAXIHP0', 'SAXIHP1', 'SAXIHP2', 'SAXIHP3', 'SAXIACP']:
            kwargs[f'i_{nm}ACLK'] = fclk[0]

            kwargs[f'i_{nm}ARVALID'] = C(0, 1)
            kwargs[f'i_{nm}ARBURST'] = C(0, 2)
            kwargs[f'i_{nm}ARLOCK'] = C(0, 2)
            kwargs[f'i_{nm}ARSIZE'] = C(0, 2)
            kwargs[f'i_{nm}ARPROT'] = C(0, 3)
            kwargs[f'i_{nm}ARCACHE'] = C(0, 4)
            kwargs[f'i_{nm}ARLEN'] = C(0, 4)
            kwargs[f'i_{nm}ARQOS'] = C(0, 4)
            if nm == 'SAXIACP':
                kwargs[f'i_{nm}ARID'] = C(0, 3)
                kwargs[f'i_{nm}ARUSER'] = C(0, 5)
            else:
                kwargs[f'i_{nm}ARID'] = C(0, 6)
            kwargs[f'i_{nm}ARADDR'] = C(0, 32)

            kwargs[f'i_{nm}AWVALID'] = C(0, 1)
            kwargs[f'i_{nm}AWBURST'] = C(0, 2)
            kwargs[f'i_{nm}AWLOCK'] = C(0, 2)
            kwargs[f'i_{nm}AWSIZE'] = C(0, 2)
            kwargs[f'i_{nm}AWPROT'] = C(0, 3)
            kwargs[f'i_{nm}AWCACHE'] = C(0, 4)
            kwargs[f'i_{nm}AWLEN'] = C(0, 4)
            kwargs[f'i_{nm}AWQOS'] = C(0, 4)
            if nm == 'SAXIACP':
                kwargs[f'i_{nm}AWID'] = C(0, 3)
                kwargs[f'i_{nm}AWUSER'] = C(0, 5)
            else:
                kwargs[f'i_{nm}AWID'] = C(0, 6)
            kwargs[f'i_{nm}AWADDR'] = C(0, 32)

            kwargs[f'i_{nm}WVALID'] = C(0, 1)
            kwargs[f'i_{nm}WLAST'] = C(0, 1)
            if nm == 'SAXIACP':
                kwargs[f'i_{nm}WID'] = C(0, 3)
            else:
                kwargs[f'i_{nm}WID'] = C(0, 6)
            if nm.startswith('SAXIGP'):
                kwargs[f'i_{nm}WDATA'] = C(0, 32)
                kwargs[f'i_{nm}WSTRB'] = C(0, 4)
            else:
                kwargs[f'i_{nm}WDATA'] = C(0, 64)
                kwargs[f'i_{nm}WSTRB'] = C(0, 8)

            kwargs[f'i_{nm}RREADY'] = C(0, 1)

            kwargs[f'i_{nm}BREADY'] = C(0, 1)

            if nm.startswith('SAXIHP'):
                kwargs[f'i_{nm}RDISSUECAP1EN'] = C(0, 1)
                kwargs[f'i_{nm}WRISSUECAP1EN'] = C(0, 1)

        # IRQs
        kwargs[f'i_IRQF2P'] = C(0, 20)

        # DMA
        for i in range(4):
            kwargs[f'i_DMA{i}ACLK'] = C(0, 1)
            kwargs[f'i_DMA{i}DAREADY'] = C(0, 1)
            kwargs[f'i_DMA{i}DRLAST'] = C(0, 1)
            kwargs[f'i_DMA{i}DRTYPE'] = C(0, 2)
            kwargs[f'i_DMA{i}DRVALID'] = C(0, 1)

        # EVENT
        kwargs[f'i_EVENTEVENTI'] = C(0, 1)

        # FTM
        kwargs[f'i_FTMDTRACEINCLOCK'] = C(0, 1)
        kwargs[f'i_FTMDTRACEINVALID'] = C(0, 1)
        kwargs[f'i_FTMDTRACEINDATA'] = C(0, 32)
        kwargs[f'i_FTMDTRACEINATID'] = C(0, 4)
        kwargs[f'i_FTMTF2PDEBUG'] = C(0, 32)
        kwargs[f'i_FTMTF2PTRIG'] = C(0, 4)
        kwargs[f'i_FTMTP2FTRIGACK'] = C(0, 4)

        # misc
        kwargs[f'i_FPGAIDLEN'] = C(1, 1)
        kwargs[f'i_DDRARB'] = C(0, 4)
        kwargs[f'i_FCLKCLKTRIGN'] = C(0xf, 4)

        # EMIO
        kwargs[f'i_EMIOGPIOI'] = C(0, 64)
        kwargs[f'i_EMIOPJTAGTCK'] = C(0, 1)
        kwargs[f'i_EMIOPJTAGTDI'] = C(0, 1)
        kwargs[f'i_EMIOPJTAGTMS'] = C(1, 1)
        kwargs[f'i_EMIOSRAMINTIN'] = C(0, 1)
        kwargs[f'i_EMIOTRACECLK'] = C(0, 1)
        kwargs[f'i_EMIOWDTCLKI'] = C(0, 1)
        for i in range(2):
            kwargs[f'i_EMIOTTC{i}CLKI'] = C(0, 3)
        for i in range(2):
            kwargs[f'i_EMIOCAN{i}PHYRX'] = C(0, 1)
        for i in range(2):
            kwargs[f'i_EMIOI2C{i}SDAI'] = C(1, 1)
            kwargs[f'i_EMIOI2C{i}SCLI'] = C(1, 1)
        for i in range(2):
            kwargs[f'i_EMIOSDIO{i}CDN'] = C(1, 1)
            kwargs[f'i_EMIOSDIO{i}CLKFB'] = C(0, 1)
            kwargs[f'i_EMIOSDIO{i}CMDI'] = C(1, 1)
            kwargs[f'i_EMIOSDIO{i}WP'] = C(1, 1)
            kwargs[f'i_EMIOSDIO{i}DATAI'] = C(0xf, 4)
        for i in range(2):
            kwargs[f'i_EMIOSPI{i}MI'] = C(1, 1)
            kwargs[f'i_EMIOSPI{i}SCLKI'] = C(1, 1)
            kwargs[f'i_EMIOSPI{i}SI'] = C(1, 1)
            kwargs[f'i_EMIOSPI{i}SSIN'] = C(1, 1)
        for i in range(2):
            kwargs[f'i_EMIOUART{i}CTSN'] = C(1, 1)
            kwargs[f'i_EMIOUART{i}DCDN'] = C(1, 1)
            kwargs[f'i_EMIOUART{i}DSRN'] = C(1, 1)
            kwargs[f'i_EMIOUART{i}RIN'] = C(1, 1)
            kwargs[f'i_EMIOUART{i}RX'] = C(1, 1)
        for i in range(2):
            kwargs[f'i_EMIOUSB{i}VBUSPWRFAULT'] = C(0, 1)
        for i in range(2):
            kwargs[f'i_EMIOENET{i}EXTINTIN'] = C(0, 1)
            kwargs[f'i_EMIOENET{i}GMIICOL'] = C(0, 1)
            kwargs[f'i_EMIOENET{i}GMIICRS'] = C(0, 1)
            kwargs[f'i_EMIOENET{i}GMIIRXCLK'] = C(0, 1)
            kwargs[f'i_EMIOENET{i}GMIIRXDV'] = C(0, 1)
            kwargs[f'i_EMIOENET{i}GMIIRXER'] = C(0, 1)
            kwargs[f'i_EMIOENET{i}GMIIRXD'] = C(0, 8)
            kwargs[f'i_EMIOENET{i}GMIITXCLK'] = C(0, 1)
            kwargs[f'i_EMIOENET{i}MDIOI'] = C(0, 1)

        rx = Signal()
        tx = Signal()

        kwargs['i_EMIOUART1RX'] = rx
        kwargs['o_EMIOUART1TX'] = tx

        m.submodules.ps = Instance('PS7', **kwargs)
        m.submodules.rst_sync = rst_sync = ResetSynchronizer(~frst[0], domain="sync")
        platform.add_clock_constraint(fclk[0], 50e6)

        m.submodules.calc = calc = Calculator(50000000, 1000000)

        m.d.comb += [
            ClockSignal('sync').eq(fclk[0]),
            rx.eq(calc.txd),
            calc.rxd.eq(tx),
        ]

        return m


plat = PynqPlatform()
plat.build(Top())
