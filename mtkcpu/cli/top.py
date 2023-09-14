#!/usr/bin/env python3
import logging
from pathlib import Path
from typing import Optional
import os

from amaranth.build.plat import Platform
from amaranth.hdl.dsl import Module

from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.global_config import Config
from mtkcpu.utils.common import EBRMemConfig, CODE_START_ADDR, MEM_START_ADDR, read_elf
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.units.mmio.bspgen import MemMapCodeGen
from mtkcpu.units.memory_interface import AddressManager
from mtkcpu.utils.linker import write_linker_script
from mtkcpu.cpu.cpu import CPU_Config

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

def get_board_cpu(elf_path : Optional[Path], cpu_config: CPU_Config):
    if elf_path:
        mem = read_elf(elf_path, verbose=False)
        # logger.info(f"ELF {elf_path} memory content: {mem}")
        logger.info(f"== read elf: {len(mem)}*4 ()= {len(mem) * 4}) bytes")
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
    return MtkCpu(mem_config=mem_config, cpu_config=cpu_config)


def get_platform() -> Platform:
    from amaranth_boards.icebreaker import ICEBreakerPlatform
    from amaranth.build.dsl import Resource, Pins, Attrs, Subsignal
    
    platform = ICEBreakerPlatform()

    # for IceBreaker board - comes from 
    # https://github.com/icebreaker-fpga/icebreaker-migen-examples/blob/master/uart/uart.py
    # 
    # The debug pins are on the PMOD1A in the following order on the connector:
    # 7 8 9 10 1 2 3 4
    # Yes that means that the pins at the edge of the board come first
    # and the pins further away from the edge second
    platform.add_resources([
        Resource(
            "debug",
            0,
            Subsignal("tms", Pins("1", dir="i", conn=("pmod", 1)), Attrs(IO_STANDARD="SB_LVCMOS")),
            Subsignal("tdi", Pins("2", dir="i", conn=("pmod", 1)), Attrs(IO_STANDARD="SB_LVCMOS")),
            Subsignal("tdo", Pins("3", dir="o", conn=("pmod", 1)), Attrs(IO_STANDARD="SB_LVCMOS")),
            Subsignal("tck", Pins("4", dir="i", conn=("pmod", 1)), Attrs(IO_STANDARD="SB_LVCMOS")),
            Attrs(IO_STANDARD="SB_LVCMOS"),
            ),
        ]
    )

    platform.add_resources(platform.break_off_pmod)

    return platform


def build(
        elf_path : Optional[Path],
        do_program: bool,
        cpu_config: CPU_Config):
    platform = get_platform()
    m = get_board_cpu(elf_path=elf_path, cpu_config=cpu_config)
    platform.build(m, do_program=do_program, nextpnr_opts="--timing-allow-fail")
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

    cpu_config = CPU_Config(
        dev_mode=False,
        with_debug=True,
        pc_reset_value=0xdeadbeef,
        with_virtual_memory=False,
    )
    
    cpu = get_board_cpu(elf_path=None, cpu_config=cpu_config)
    platform = get_platform()
    dummy_elaborate(cpu, platform)
    arbiter = cpu.arbiter
    assert isinstance(arbiter, AddressManager)
    owners, schemes = zip(*arbiter.get_mmio_devices_config())
    MemMapCodeGen.gen_bsp_sources(owners, schemes)

def main():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    sp = parser.add_subparsers(required=True, dest="command")
    
    build_p = sp.add_parser("build", help="Build the IceBreaker bitstream containing full SoC.")
    build_p.add_argument("--no_dm", action="store_true")
    build_p.add_argument("--dev_mode", action="store_true")
    build_p.add_argument("--with_virtual_memory", action="store_true")
    build_p.add_argument("-e", "--elf", type=Path, help="Path to an .elf file to initialize Block RAM with.")
    build_p.add_argument("-p", "--program", action="store_true")
    
    sp.add_parser("gen_bsp", help="Generate bsp .c and .h sources, based on SoC address space.")
    sp.add_parser("gen_linker_script", help="Generate linker script, based on SoC address space.")
    
    args = parser.parse_args()


    if args.command == "build":
        cpu_config = CPU_Config(
            with_debug=(not args.no_dm),
            dev_mode=args.dev_mode,
            pc_reset_value=CODE_START_ADDR,
            with_virtual_memory=args.with_virtual_memory,
        )
        build(
            elf_path=args.elf,
            do_program=args.program,
            cpu_config=cpu_config,
        )
    elif args.command == "gen_bsp":
        generate_bsp()
    elif args.command == "gen_linker_script":
        out_path = Config.sw_dir / "common" / "linker.ld"
        mem_addr = MEM_START_ADDR
        mem_size_kb = 1 # TODO pass as a command line param
        write_linker_script(out_path=out_path, mem_addr=mem_addr, mem_size_kb=mem_size_kb)
    

if __name__ == "__main__":
    main()
