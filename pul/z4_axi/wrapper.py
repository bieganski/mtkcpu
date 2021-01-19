from nmigen import *
from nmigen.vendor.xilinx_7series import *
from nmigen_boards.resources import *
from nmigen.build import *
from nmigen.lib.cdc import ResetSynchronizer
from accelerator import Accelerator
from axi import AxiInterface


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

        maxigp0 = AxiInterface(32, 12)
        saxihp0 = AxiInterface(64, 6)
        m.submodules.accel = accel = Accelerator(maxigp0, saxihp0)

        kwargs['i_MAXIGP0ARREADY'] = maxigp0.ar_ready
        kwargs['o_MAXIGP0ARVALID'] = maxigp0.ar_valid
        kwargs['o_MAXIGP0ARBURST'] = maxigp0.ar_burst
        kwargs['o_MAXIGP0ARSIZE'] = maxigp0.ar_size
        kwargs['o_MAXIGP0ARLEN'] = maxigp0.ar_len
        kwargs['o_MAXIGP0ARLOCK'] = maxigp0.ar_lock
        kwargs['o_MAXIGP0ARPROT'] = maxigp0.ar_prot
        kwargs['o_MAXIGP0ARCACHE'] = maxigp0.ar_cache
        kwargs['o_MAXIGP0ARQOS'] = maxigp0.ar_qos
        kwargs['o_MAXIGP0ARID'] = maxigp0.ar_id
        kwargs['o_MAXIGP0ARADDR'] = maxigp0.ar_addr

        kwargs['i_MAXIGP0AWREADY'] = maxigp0.aw_ready
        kwargs['o_MAXIGP0AWVALID'] = maxigp0.aw_valid
        kwargs['o_MAXIGP0AWBURST'] = maxigp0.aw_burst
        kwargs['o_MAXIGP0AWSIZE'] = maxigp0.aw_size
        kwargs['o_MAXIGP0AWLEN'] = maxigp0.aw_len
        kwargs['o_MAXIGP0AWLOCK'] = maxigp0.aw_lock
        kwargs['o_MAXIGP0AWPROT'] = maxigp0.aw_prot
        kwargs['o_MAXIGP0AWCACHE'] = maxigp0.aw_cache
        kwargs['o_MAXIGP0AWQOS'] = maxigp0.aw_qos
        kwargs['o_MAXIGP0AWID'] = maxigp0.aw_id
        kwargs['o_MAXIGP0AWADDR'] = maxigp0.aw_addr

        kwargs['i_MAXIGP0WREADY'] = maxigp0.w_ready
        kwargs['o_MAXIGP0WVALID'] = maxigp0.w_valid
        kwargs['o_MAXIGP0WLAST'] = maxigp0.w_last
        kwargs['o_MAXIGP0WID'] = maxigp0.w_id
        kwargs['o_MAXIGP0WSTRB'] = maxigp0.w_strb
        kwargs['o_MAXIGP0WDATA'] = maxigp0.w_data

        kwargs['o_MAXIGP0BREADY'] = maxigp0.b_ready
        kwargs['i_MAXIGP0BVALID'] = maxigp0.b_valid
        kwargs['i_MAXIGP0BID'] = maxigp0.b_id
        kwargs['i_MAXIGP0BRESP'] = maxigp0.b_resp

        kwargs['o_MAXIGP0RREADY'] = maxigp0.r_ready
        kwargs['i_MAXIGP0RVALID'] = maxigp0.r_valid
        kwargs['i_MAXIGP0RLAST'] = maxigp0.r_last
        kwargs['i_MAXIGP0RID'] = maxigp0.r_id
        kwargs['i_MAXIGP0RRESP'] = maxigp0.r_resp
        kwargs['i_MAXIGP0RDATA'] = maxigp0.r_data

        kwargs['o_SAXIHP0ARREADY'] = saxihp0.ar_ready
        kwargs['i_SAXIHP0ARVALID'] = saxihp0.ar_valid
        kwargs['i_SAXIHP0ARBURST'] = saxihp0.ar_burst
        kwargs['i_SAXIHP0ARSIZE'] = saxihp0.ar_size
        kwargs['i_SAXIHP0ARLEN'] = saxihp0.ar_len
        kwargs['i_SAXIHP0ARLOCK'] = saxihp0.ar_lock
        kwargs['i_SAXIHP0ARPROT'] = saxihp0.ar_prot
        kwargs['i_SAXIHP0ARCACHE'] = saxihp0.ar_cache
        kwargs['i_SAXIHP0ARQOS'] = saxihp0.ar_qos
        kwargs['i_SAXIHP0ARID'] = saxihp0.ar_id
        kwargs['i_SAXIHP0ARADDR'] = saxihp0.ar_addr

        kwargs['o_SAXIHP0AWREADY'] = saxihp0.aw_ready
        kwargs['i_SAXIHP0AWVALID'] = saxihp0.aw_valid
        kwargs['i_SAXIHP0AWBURST'] = saxihp0.aw_burst
        kwargs['i_SAXIHP0AWSIZE'] = saxihp0.aw_size
        kwargs['i_SAXIHP0AWLEN'] = saxihp0.aw_len
        kwargs['i_SAXIHP0AWLOCK'] = saxihp0.aw_lock
        kwargs['i_SAXIHP0AWPROT'] = saxihp0.aw_prot
        kwargs['i_SAXIHP0AWCACHE'] = saxihp0.aw_cache
        kwargs['i_SAXIHP0AWQOS'] = saxihp0.aw_qos
        kwargs['i_SAXIHP0AWID'] = saxihp0.aw_id
        kwargs['i_SAXIHP0AWADDR'] = saxihp0.aw_addr

        kwargs['o_SAXIHP0WREADY'] = saxihp0.w_ready
        kwargs['i_SAXIHP0WVALID'] = saxihp0.w_valid
        kwargs['i_SAXIHP0WLAST'] = saxihp0.w_last
        kwargs['i_SAXIHP0WID'] = saxihp0.w_id
        kwargs['i_SAXIHP0WSTRB'] = saxihp0.w_strb
        kwargs['i_SAXIHP0WDATA'] = saxihp0.w_data

        kwargs['i_SAXIHP0BREADY'] = saxihp0.b_ready
        kwargs['o_SAXIHP0BVALID'] = saxihp0.b_valid
        kwargs['o_SAXIHP0BID'] = saxihp0.b_id
        kwargs['o_SAXIHP0BRESP'] = saxihp0.b_resp

        kwargs['i_SAXIHP0RREADY'] = saxihp0.r_ready
        kwargs['o_SAXIHP0RVALID'] = saxihp0.r_valid
        kwargs['o_SAXIHP0RLAST'] = saxihp0.r_last
        kwargs['o_SAXIHP0RID'] = saxihp0.r_id
        kwargs['o_SAXIHP0RRESP'] = saxihp0.r_resp
        kwargs['o_SAXIHP0RDATA'] = saxihp0.r_data

        m.submodules.ps = Instance('PS7', **kwargs)
        m.submodules.rst_sync = rst_sync = ResetSynchronizer(~frst[0], domain="sync")
        platform.add_clock_constraint(fclk[0], 50e6)

        m.d.comb += [
            ClockSignal('sync').eq(fclk[0]),
        ]

        return m


plat = PynqPlatform()
plat.build(Top())
