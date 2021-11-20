#!/usr/bin/env python3
import logging
from os import confstr
from pathlib import Path
from typing import Optional

from nmigen.hdl.dsl import Module
from nmigen_boards.icebreaker import ICEBreakerPlatform

from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.global_config import Config
from mtkcpu.utils.common import EBRMemConfig, CODE_START_ADDR, read_elf
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.units.mmio.bspgen import MemMapCodeGen
from mtkcpu.units.memory_interface import AddressManager

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

def get_board_cpu(elf_path : Optional[Path]):
    if elf_path:
        mem = read_elf(elf_path, verbose=False)
        # logger.info(f"ELF {elf_path} memory content: {mem}")
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

def build(elf_path : Path, do_program=True):
    plat = ICEBreakerPlatform()
    m = get_board_cpu(elf_path=elf_path)
    plat.build(m, do_program=do_program)


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--build", type=str, help="Name of project inside sw/ to compile into hw. and run on a board.")
    parser.add_argument("--program", action="store_true")
    parser.add_argument("--gen_bsp", action="store_true")
    parser.add_argument("--sim", type=str, help="Name of project inside sw/ to compile and sim.")
    # parser.add_argument("--elf", type=Path, help="ELF to be used for build/sim")
    args = parser.parse_args()

    from nmigen import Elaboratable, Instance
    from nmigen.build.plat import Platform
    
    # partially taken from nmigen/dsl.py (Module.elaborate method)
    # needs to be called for bsp generation, as some objects attrs are set during 'elaborate()'
    # e.g. instantiating GPIO block needs platform.request calls (e.g. for LED), that's why it's done
    # in 'elaborate(self, platform).
    def dummy_elaborate(e : Elaboratable, plat : Platform):
        root : Module = e.elaborate(plat)
        if isinstance(root, Instance):
            return
        for name in root._named_submodules:
            e = root._named_submodules[name]
            dummy_elaborate(e, plat)
        for e in root._anon_submodules:
            dummy_elaborate(e, plat)

    if args.build:
        proj_name = args.build
        from mtkcpu.utils.tests.utils import compile_sw_project
        elf_path = compile_sw_project(proj_name)
        build(elf_path=elf_path, do_program=args.program)
    elif args.gen_bsp:
        cpu = get_board_cpu(elf_path=args.elf)
        arbiter = cpu.arbiter
        plat = ICEBreakerPlatform()
        dummy_elaborate(arbiter, plat)
        assert isinstance(arbiter, AddressManager)
        owners, schemes = zip(*arbiter.get_mmio_devices_config())
        MemMapCodeGen.gen_bsp_sources(owners, schemes)
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