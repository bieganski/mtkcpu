#!/usr/bin/env python3
import logging
from pathlib import Path
from typing import Optional
import os

from amaranth.build.plat import Platform
from amaranth.hdl.dsl import Module

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


def get_platform() -> Platform:
    from nmigen_boards.icebreaker import ICEBreakerPlatform
    from amaranth.build.dsl import Resource, Pins, Attrs
    
    platform = ICEBreakerPlatform()

    # for IceBreaker board - comes from 
    # https://github.com/icebreaker-fpga/icebreaker-migen-examples/blob/master/uart/uart.py
    # 
    # The debug pins are on the PMOD1A in the following order on the connector:
    # 7 8 9 10 1 2 3 4
    # Yes that means that the pins at the edge of the board come first
    # and the pins further away from the edge second
    platform.add_resources([
        Resource("debug", 0, Pins("7 8 9 10 1 2 3 4", dir="o",
                                    conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS"))
    ])

    return platform
    

def build(elf_path : Path, do_program=True):
    platform = get_platform()
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
