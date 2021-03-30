#!/usr/bin/env python3
import io
from ppci.api import cc, link, asm


source_file = io.StringIO(
    # """
    # .section code
    #     sw x31, 4(x7)
    #     add x1, x1, x1
    #     addi x1, x1, 10
    #     sub x1, x1, x1
    #     beq x0, x0, a
    #     a:
    #     nop
    # """

    f"""
        .section code
            jalr x10, x8, 0x0
        """
)


def dump_asm_to_S_file(val_lst, filename="asm.S", verbose=False):
    import os
    if os.path.isfile(filename):
        # raise ValueError(f"Error: File {filename} already exists!")
        os.remove(filename)
    with open(filename, "w") as f:
        for instr in val_lst:
            assert type(instr) == int
        f.writelines("\n /* This file was dumped automatically */\n")
        f.writelines([f".word {hex(instr)} /* {format(instr, '032b')} */\n" for instr in val_lst])
    LOG(f"OK, file '{filename}'' dumped!", verbose=verbose)

    import subprocess

    obj_filename = filename.split('.')[-2] + ".o"
    subprocess.getoutput(f"riscv-none-embed-gcc -c {filename} -o {obj_filename}")
    output = subprocess.getoutput(f"riscv-none-embed-objdump -d {obj_filename}")
    LOG(output, verbose=verbose)

# https://stackoverflow.com/a/312464
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def LOG(*args, **kwargs):
    # if 'verbose' not in kwargs or 
    if not kwargs['verbose']:
        return
    kwargs.pop('verbose')
    print(*args, **kwargs)

# returns bytearray with asm.
def dump_asm(string, verbose=False):

    # from ppci.common import CompilerError
    obj = asm(string, 'riscv')
    # try:
    #     obj = asm(source_file, 'riscv')
    #     print("ASM succeeded...")
    # except CompilerError:
    #     print("ASM didn't work, trying CC...")
    #     obj = cc(source_file, 'riscv')
    obj = link([obj])
    # print(obj.sections)
    code = obj.get_section('code').data
    # from pprint import pprint
    # pprint(dir(obj))
    # s = obj.get_symbol('printf')
    # print(dir(s))
    LOG(code, verbose=verbose)

    code = [int.from_bytes(x, 'little') for x in chunks(code, 4)] # 4 byte chunks
    LOG([hex(instr) for instr in code], verbose=verbose)
    LOG(code, verbose=verbose)
    for i, instr in enumerate(code, 1):
        LOG(f"{i}: {format(instr, '032b')} ", verbose=verbose)

    LOG("====================================", verbose=verbose)
    for i, instr in enumerate(code, 1):
        shift = 32
        l = [7, 5, 5, 3, 5, 7] # funct7, r2, r1, funct3, rd, opcode
        LOG(f"{i}: ", end='', verbose=verbose)
        for s in l:
            shift -= s
            f = f"{format(instr >> shift & (2**s-1), f'0{s}b')}"
            LOG(f"{f},", end='', verbose=verbose)
        LOG("", verbose=verbose)

    dump_asm_to_S_file(code, verbose=verbose)
    return code

if __name__ == "__main__":
    dump_asm(source_file, verbose=True)

