#!/usr/bin/env python3
import logging
from pathlib import Path
from typing import Optional
import os

from amaranth.build.plat import Platform
from amaranth.hdl.dsl import Module
from amaranth import *

from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.global_config import Config
from mtkcpu.utils.common import EBRMemConfig, CODE_START_ADDR, read_elf
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.units.mmio.bspgen import MemMapCodeGen
from mtkcpu.units.memory_interface import AddressManager

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

def get_board_cpu(elf_path : Optional[Path] = None):
    if elf_path:
        mem = read_elf(elf_path, verbose=False)
        # logger.info(f"ELF {elf_path} memory content: {mem}")
        print(f"== read elf: {len(mem)}*4 bytes = {len(mem) * 4} bytes")
        mem_config = EBRMemConfig.from_mem_dict(
            simulate=False,
            start_addr=CODE_START_ADDR,
            num_bytes=1024,
            mem_dict=MemoryContents(mem)
        )
    else:
        mem_config = EBRMemConfig(
            mem_size_words=10, # TODO should we allow empty memory?
            mem_content_words=None,
            mem_addr=CODE_START_ADDR,
            simulate=False
        )
    return MtkCpu(mem_config=mem_config)


# def get_platform() -> Platform:
#     from nmigen_boards.icebreaker import ICEBreakerPlatform
    
#     platform = ICEBreakerPlatform()

#     # for IceBreaker board - comes from 
#     # https://github.com/icebreaker-fpga/icebreaker-migen-examples/blob/master/uart/uart.py
#     # 
#     # The debug pins are on the PMOD1A in the following order on the connector:
#     # 7 8 9 10 1 2 3 4
#     # Yes that means that the pins at the edge of the board come first
#     # and the pins further away from the edge second
#     from amaranth.build.dsl import Resource, Pins, Attrs

#     platform.add_resources([
#         Resource("debug", 0, Pins("7 8 9 10 1 2 3 4", dir="o",
#                                     conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS"))
#     ])

#     return platform

from amaranth.vendor.xilinx_7series import Xilinx7SeriesPlatform

class PynqPlatform(Xilinx7SeriesPlatform):
    device = 'xc7z020'
    package = 'clg400'
    speed = '1'

    # XXX
    from nmigen_boards.icebreaker import ICEBreakerPlatform

    from nmigen_boards.resources import RGBLEDResource, LEDResources, SwitchResources, ButtonResources, UARTResource
    from amaranth.build.dsl import Resource, Pins, Attrs, Clock

    resources = [
        Resource("clk125", 0, Pins("H16", dir="i"), Clock(125e6), Attrs(IOSTANDARD="LVCMOS33")),
        *LEDResources(pins="R14 P14 N16 M14", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        RGBLEDResource(0, r="N15", g="G17", b="L15", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        RGBLEDResource(1, r="M15", g="L14", b="G14", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        *ButtonResources(pins="D19 D20 L20 L19", attrs=Attrs(IOSTANDARD="LVCMOS33")),
        *SwitchResources(pins="M20 M19", attrs=Attrs(IOSTANDARD="LVCMOS33")),

        # Resource("led_r", 1, Pins("7", dir="o", conn=("pmod", 2)),
        #          Attrs(IO_STANDARD="SB_LVCMOS")),
        # Resource("led_g", 1, Pins("1", dir="o", conn=("pmod", 2)),
        #          Attrs(IO_STANDARD="SB_LVCMOS")),

        Resource("led_r", 0, Pins("R14", dir="o"), Attrs(IO_STANDARD="LVCMOS33")),
        Resource("led_g", 0, Pins("P14", dir="o"), Attrs(IO_STANDARD="LVCMOS33")),


        UARTResource(0,
            rx="6", tx="9",
            attrs=Attrs(IO_STANDARD="SB_LVTTL", PULLUP=1)
        ),

        Resource("debug", 0, Pins("7 8 9 10 1 2 3 4", dir="o",
                                    conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS"))
    ]
    connectors = []



def get_platform() -> Platform:
    return PynqPlatform()

class AxiInterface:
    def __init__(self, data_width, id_width):
        self.data_width = data_width
        self.id_width = id_width

        self.ar_ready = Signal()
        self.ar_valid = Signal()
        self.ar_burst = Signal(2)
        self.ar_size = Signal(2)
        self.ar_len = Signal(4)
        self.ar_lock = Signal(2)
        self.ar_prot = Signal(3)
        self.ar_cache = Signal(4)
        self.ar_qos = Signal(4)
        self.ar_id = Signal(id_width)
        self.ar_addr = Signal(32)

        self.aw_ready = Signal()
        self.aw_valid = Signal()
        self.aw_burst = Signal(2)
        self.aw_size = Signal(2)
        self.aw_len = Signal(4)
        self.aw_lock = Signal(2)
        self.aw_prot = Signal(3)
        self.aw_cache = Signal(4)
        self.aw_qos = Signal(4)
        self.aw_id = Signal(id_width)
        self.aw_addr = Signal(32)

        self.w_ready = Signal()
        self.w_valid = Signal()
        self.w_last = Signal()
        self.w_id = Signal(id_width)
        self.w_strb = Signal(data_width // 8)
        self.w_data = Signal(data_width)

        self.b_ready = Signal()
        self.b_valid = Signal()
        self.b_id = Signal(id_width)
        self.b_resp = Signal(2)

        self.r_ready = Signal()
        self.r_valid = Signal()
        self.r_last = Signal()
        self.r_id = Signal(id_width)
        self.r_resp = Signal(2)
        self.r_data = Signal(data_width)


class Top(Elaboratable):
    def __init__(self, cpu: Elaboratable) -> None:
        self.cpu = cpu
        super().__init__()

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
        
        # XXX
        # from accelerator import Accelerator
        # m.submodules.accel = accel = Accelerator(maxigp0, saxihp0)

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
        from nmigen.lib.cdc import ResetSynchronizer
        from nmigen import ClockSignal
        m.submodules.rst_sync = rst_sync = ResetSynchronizer(~frst[0], domain="sync")
        platform.add_clock_constraint(fclk[0], 50e6)

        m.d.comb += [
            ClockSignal('sync').eq(fclk[0]),
        ]

        m.submodules.cpu = self.cpu

        return m

    

def build(elf_path : Path, do_program=True):
    platform = get_platform()

    from pathlib import Path
    root_dir = Path(__file__).parent.parent.parent.absolute()
    nextpnr_dir=str(root_dir / "nextpnr-xilinx")
    plat = PynqPlatform(toolchain='yosys_nextpnr')
    
    cpu = get_board_cpu(elf_path=elf_path)

    top = Top(cpu=cpu)

    plat.build(top, nextpnr_dir=nextpnr_dir)

    return


    m = get_board_cpu(elf_path=elf_path)
    platform.build(m, do_program=do_program)
    logger.info(f"OK, Design was built successfully, printing out some stats..")
    timing_report = Path("build/top.tim")
    if not timing_report.exists():
        raise ValueError(f"ERROR: Could not find {timing_report} timing report file in build artifacts!")
    lines = timing_report.open().readlines()

    def find_pattern_idx(lst, pat) -> Optional[int]:
        maybe = [x for x in lst if pat in x]
        try:
            return lst.index(maybe[0])
        except:
            return None

    max_freq_idx = find_pattern_idx(lines, "Max frequency for clock")
    resources_idx = find_pattern_idx(lines, "Info: Device utilisation")
    if not all([max_freq_idx, resources_idx]):
        raise ValueError(f"Layout of {timing_report} file does not match predefined one!")
    print(lines[max_freq_idx])
    print("".join(lines[resources_idx:resources_idx+16])) # TODO probably more lines for different architectures



from amaranth import Elaboratable, Instance
from amaranth.build.plat import Platform
    
# partially taken from amaranth/dsl.py (Module.elaborate method)
# needs to be called for bsp generation, as some objects attrs are set during 'elaborate()'
# e.g. instantiating GPIO block needs platform.request calls (e.g. for LED), that's why it's done
# in 'elaborate(self, platform).
def dummy_elaborate(e : Elaboratable, platform : Platform):
    e._MustUse__used = True
    root : Module = e.elaborate(platform)
    root._MustUse__used = True
    if isinstance(root, Instance):
        return
    for name in root._named_submodules:
        e = root._named_submodules[name]
        dummy_elaborate(e, platform)
    for e in root._anon_submodules:
        dummy_elaborate(e, platform)

def generate_bsp():
    sw_bsp_path = os.path.join(os.path.dirname(__file__), "..", "..", "sw", "bsp")
    print(f"sw_bsp_path = {sw_bsp_path}")
    Path(sw_bsp_path).mkdir(parents=True, exist_ok=True)
    cpu = get_board_cpu()
    platform = get_platform()
    dummy_elaborate(cpu, platform)
    arbiter = cpu.arbiter
    assert isinstance(arbiter, AddressManager)
    owners, schemes = zip(*arbiter.get_mmio_devices_config())
    MemMapCodeGen.gen_bsp_sources(owners, schemes)

def main():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--build_design_with_elf", type=str, help="Path to an .elf file to be embedded into bitstream")
    parser.add_argument("--program", action="store_true")
    parser.add_argument("--gen_bsp", action="store_true")
    parser.add_argument("--gen_linker_script", action="store_true")
    parser.add_argument("--sim", type=str, help="Name of project inside sw/ to compile and sim.")
    # parser.add_argument("--elf", type=Path, help="ELF to be used for build/sim")
    args = parser.parse_args()


    if args.build_design_with_elf:
        elf_path = args.build_design_with_elf
        build(elf_path=elf_path, do_program=args.program)
    elif args.gen_bsp:
        generate_bsp()
    elif args.gen_linker_script:
        from mtkcpu.utils.linker import write_linker_script
        from mtkcpu.global_config import Config
        out_path = Config.sw_dir / "common" / "linker.ld"
        from mtkcpu.utils.common import CODE_START_ADDR
        mem_addr = CODE_START_ADDR
        mem_size_kb = 1 # TODO pass as a command line param
        logging.info(f"writing linker script to {out_path}, addr: {hex(mem_addr)} of size {mem_size_kb} kb..")
        write_linker_script(out_path, mem_addr, mem_size_kb)
    elif args.sim:
        from mtkcpu.utils.tests.utils import CpuTestbenchCase, cpu_testbench_test
        proj_name = args.sim
        projects = [x.name for x in Config.sw_dir.iterdir() if x.is_dir()]
        if not proj_name in projects:
            raise ValueError(f"Project sw/{proj_name} does not exists! Try one of following: {projects}")
        
        cpu_testbench_test(
            CpuTestbenchCase(
                name=f"simulate project: sw/{proj_name}",
                try_compile=True,
                elf_path=Config.sw_dir / proj_name / "build" / f"{proj_name}.elf"
            )
        )
    else:
        if args.program:
            logger.error("Cannot --program without previous --build!")
            exit(1)
        logger.error("ERORR: exactly one of --build or --gen_bsp param must be passed!") # TODO allow both
        exit(1)
    

if __name__ == "__main__":
    main()
