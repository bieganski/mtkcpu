#!/usr/bin/env python3
from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.utils.common import EBRMemConfig, START_ADDR, read_elf
from mtkcpu.utils.tests.memory import MemoryContents

from nmigen_boards.icebreaker import ICEBreakerPlatform

def main():
    plat = ICEBreakerPlatform()
    
    mem_config = EBRMemConfig.from_mem_dict(
        start_addr=START_ADDR,
        num_bytes=256,
        mem_dict=MemoryContents(
            read_elf("/home/mateusz/github/mtkcpu/elf/example.elf", verbose=False)
        )
    )

    m = MtkCpu(mem_config=mem_config)
    plat.build(m, do_program=True)


if __name__ == "__main__":
    main()