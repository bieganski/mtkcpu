from functools import reduce
from itertools import starmap
from operator import or_
from dataclasses import dataclass
from typing import List, Optional
from itertools import count
from mtkcpu.asm.asm_dump import bytes_to_u32_arr, dump_instrs

MEM_START_ADDR = 0x1000
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

@dataclass(frozen=True)
class EBRMemConfig():
    word_size = 4
    mem_size_words : int
    mem_content_words : Optional[List[int]] # e.g you may want to have an ELF content as an init state
    mem_addr : int
    simulate: bool

    from mtkcpu.utils.tests.memory import MemoryContents

    @staticmethod
    def from_mem_dict(start_addr: int , num_bytes: int, mem_dict: MemoryContents, simulate: bool) -> "EBRMemConfig":
        ws = __class__.word_size
        num_words = num_bytes // ws
        
        d = dict([(k - start_addr, v) for k, v in mem_dict.memory.items()])
        if any([x < 0 for x in d.keys()]) or any([x >= num_bytes for x in d.keys()]):
            raise ValueError(f"Passed MemoryContents contains initialized memory on addresses"
                f"that doesn't fit into range [{start_addr}, {start_addr + num_bytes}]!"
                f"(tried {mem_dict.memory})"
            )
        from math import log2
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

def compile_source(source_raw, output_elf_fname):
    from subprocess import Popen, PIPE
    from pathlib import Path
    import tempfile
    
    COMPILER = "riscv-none-embed-gcc"
    GIT_ROOT = Path(Popen(['git', 'rev-parse', '--show-toplevel'], stdout=PIPE).communicate()[0].rstrip().decode('utf-8'))
    LINKER_SCRIPT = GIT_ROOT / "./elf/linker.ld"
    
    p = Popen(["which", COMPILER], stdout=PIPE)
    _, _ = p.communicate()
    if p.returncode != 0:
        raise ValueError(f"Error! Cannot find {COMPILER} compiler in your PATH!")

    
    tmp_dir = tempfile.mkdtemp()
    asm_filename = f"{tmp_dir}/tmp.S"

    with open(asm_filename, 'w+') as asm_file:
        asm_file.write(source_raw)

    p = Popen([COMPILER, "-nostartfiles", f"-T{LINKER_SCRIPT}", asm_filename, "-o", output_elf_fname], stdout=PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise ValueError(f"Compilation error! source {source_raw}\ncouldn't get compiled! Error msg: \n{out}\n\n{err}")


