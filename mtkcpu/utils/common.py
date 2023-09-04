from functools import reduce
from itertools import starmap, count
import logging
from operator import or_
from dataclasses import dataclass
from typing import List, Optional
from subprocess import Popen, PIPE
from pathlib import Path
from shutil import which
from tempfile import NamedTemporaryFile

from mtkcpu.asm.asm_dump import bytes_to_u32_arr, dump_instrs

MEM_START_ADDR = 0x8000_0000
CODE_START_ADDR = MEM_START_ADDR


# https://github.com/lambdaconcept/minerva/blob/master/minerva/units/decoder.py
def matcher(encodings):
    return lambda opcode, funct3, funct7: reduce(
        or_,
        starmap(
            lambda opc, f3=None, f7=None: (
                opcode == opc if opc is not None else 1
            )
            & (funct3 == f3 if f3 is not None else 1)
            & (funct7 == f7 if f7 is not None else 1),
            encodings,
        ),
    )

from math import log2, ceil
from mtkcpu.utils.tests.memory import MemoryContents


@dataclass(frozen=True)
class EBRMemConfig():
    word_size = 4
    mem_size_words : int
    mem_content_words : Optional[List[int]] # e.g you may want to have an ELF content as an init state
    mem_addr : int
    simulate: bool

    @property
    def last_valid_addr_excl(self):
        return self.mem_addr + self.mem_size_words * self.word_size
    
    @property
    def arena_kb_ceiled(self):
        ceil(self.word_size * self.mem_size_words / 1024)
        return self.mem_addr + self.mem_size_words * self.word_size

    @staticmethod
    def from_mem_dict(start_addr: int , num_bytes: int, mem_dict: MemoryContents, simulate: bool) -> "EBRMemConfig":
        ws = __class__.word_size
        num_words = num_bytes // ws
        
        d = dict([(k - start_addr, v) for k, v in mem_dict.memory.items()])
        if any([x < 0 for x in d.keys()]) or any([x >= num_bytes for x in d.keys()]):
            valid_range_fmt = f"[{hex(start_addr), hex(start_addr + num_bytes)}]"
            non_matching = [x for x in d.keys() if x < start_addr or x >= start_addr + num_bytes][0]
            raise ValueError(f"Passed MemoryContents contains initialized memory on addresses "
                f"that doesn't fit into range {valid_range_fmt}!"
                f"(tried {mem_dict if len(mem_dict.memory) < 100 else f'<too big to print> (of length {len(mem_dict.memory)}'}."
                f"E.g. {hex(non_matching)}={hex(d[non_matching])} not matches.)"
            )
        mem_map = [0] * num_words
        # raise ValueError(num_words, int(log2(ws)), [k - start_addr for k in d.keys()])
        for k, v in d.items():
            mem_map[(k >> int(log2(ws)))] = v

        return EBRMemConfig(
            mem_size_words=num_words,
            mem_addr=start_addr,
            mem_content_words=mem_map,
            simulate=simulate,
        )

# returns memory (all PT_LOAD type segments) as dictionary.
def read_elf(elf_path, verbose=False):
    from elftools.elf.elffile import ELFFile
    handle = open(elf_path, 'rb')
    elf = ELFFile(handle)
    
    if verbose:
        import subprocess
        p = subprocess.Popen(["riscv-none-embed-objdump", "--disassembler-options=no-aliases",  "-M",  "numeric", "-d", elf_path], stdout=subprocess.PIPE)
        out, _ = p.communicate()
        out = str(out.decode("ascii"))
        raise ValueError(out)
        
    # for each segment that is being loaded into memory
    # retrieve it's data and put in 'mem' dict (both code and program data). 
    mem = {}
    for s in elf.iter_segments():
        file_offset, data_len = s.header.p_offset, s.header.p_memsz
        load_addr = s.header.p_vaddr
        handle.seek(file_offset)
        raw = handle.read(data_len)
        data = bytes_to_u32_arr(raw)
        if verbose:
            dump_instrs(data)
        segment_mem = dict(zip(count(load_addr, 4), data))
        mem.update(segment_mem)
    return mem

# TODO pass additional param
def compile_source(source_raw : str, output_elf : Path, mem_size_kb: int):
    
    COMPILERS = ["riscv-none-embed-gcc", "riscv-none-elf-gcc"]
    for candicate in COMPILERS:
        if which(candicate) is not None:
            break
    else:
        raise ValueError(f"Could not find a suitable compiler! Seeked for {COMPILERS}")
    
    compiler = candicate
    
    with NamedTemporaryFile(suffix=".S", delete=False, mode="w+") as asm_file:
        assert asm_file.write(source_raw)
    with NamedTemporaryFile(suffix=".ld", delete=False) as ld_file:
        from mtkcpu.utils.linker import write_linker_script
        write_linker_script(Path(ld_file.name), mem_addr=CODE_START_ADDR, mem_size_kb=mem_size_kb)
    
    march = "rv32i"
    if "elf" in compiler:
        march += "_zicsr"

    cmd = [compiler, f"-march={march}", "-mabi=ilp32", "-nostartfiles", f"-T{ld_file.name}", asm_file.name, "-o", output_elf]
    logging.critical(" ".join(cmd))
    p = Popen(cmd, stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise ValueError(f"Compilation error! source {source_raw}\ncouldn't get compiled! Error msg: \n{out}\n\n{err}")
    else:
        logging.info(f"OK, ELF file created! {output_elf}")
        logging.info(out)
        logging.info(err)


