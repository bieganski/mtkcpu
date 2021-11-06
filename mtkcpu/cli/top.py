#!/usr/bin/env python3
from typing import List

from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.units.loadstore import WishboneBusRecord
from mtkcpu.utils.common import EBRMemConfig, CODE_START_ADDR, read_elf
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.units.mmio.bspgen import BspGeneratable, MemMapCodeGen, MMIOPeriphConfig

from nmigen_boards.icebreaker import ICEBreakerPlatform


def get_board_cpu():
    mem_config = EBRMemConfig.from_mem_dict(
        simulate=False,
        start_addr=CODE_START_ADDR,
        num_bytes=256,
        mem_dict=MemoryContents(
            read_elf("/home/mateusz/github/mtkcpu/elf/example.elf", verbose=False)
        )
    )

    return MtkCpu(mem_config=mem_config)

def build(do_program=True):
    plat = ICEBreakerPlatform()
    m = get_board_cpu()
    plat.build(m, do_program=True)

def main():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--program", action="store_true")
    parser.add_argument("--gen_bsp", action="store_true")
    args = parser.parse_args()

    if args.build:
        build(do_program=args.program)
    elif args.gen_bsp:
        cpu = get_board_cpu()
        arbiter = cpu.arbiter
        plat = ICEBreakerPlatform()
        # from mtkcpu.units.mmio.gpio import GPIO_Wishbone 
        # assert isinstance(GPIO_Wishbone(WishboneBusRecord(), [1]), BspGeneratable)
        m = arbiter.elaborate(platform=plat) # needs to be called as some objects attrs are set during 'elaborate()'
        # maybe_mmio_blocks = m.submodules._builder.__dict__['_named_submodules']
        # mmio_blocks : List[MMIOPeriphConfig] = []
        # for k, v in maybe_mmio_blocks.items():
        #     if not isinstance(v, BspGeneratable):
        #         continue
        #     else:
        #         print(f"Found bsp generatable module {k}..")
        #         mmio_blocks.append(v)

        # TODO this way is ugly
        # from design point of view we don't want BusOwner to know it's starting address 
        # (thus MMIOPeriphConfig don't have that info).
        # from bsp codegen point of view we need that info to set base address C variable.
        configs = arbiter.addressing_configs_bsp_gen
        periph_configs=[]
        assert configs
        for (start, num_words), mmio_block in configs:
            assert isinstance(mmio_block, BspGeneratable)
            cfg = mmio_block.get_periph_config()
            cfg.first_valid_addr = start
            ws = 4 # TODO
            cfg.last_valid_addr = start + ws * num_words
            periph_configs.append(cfg)

        codegen = MemMapCodeGen(periph_configs=periph_configs)
        codegen.gen_bsp_sources()
        
    else:
        if args.program:
            print("Cannot --program without previous --build!")
            exit(1)
        print("ERORR: exactly one of --build or --gen_bsp param must be passed!") # TODO allow both
        exit(1)
    

if __name__ == "__main__":
    main()