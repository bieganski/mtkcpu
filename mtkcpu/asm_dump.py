#!/usr/bin/env python3
import io
from ppci.api import cc, link, asm

source_file = io.StringIO(
    """
        int printf(char* fmt) { }
        void main() {
            printf("Hello world!\n");
        }
    """
)

source_file = io.StringIO(
    """
    .section code
        lw t0, 0(t1)
        li t1, 0xdeadbeef
        sb t1, 0(t1)
        sw t1, 0(t1)
        srai x2, x1, 4
        beq t1, t2, a ; 0(t2)
        a:
        nop
        b: .word 8082
        srli x3, x1, 4
    """
)

source_file = io.StringIO(
    """
    .section code
        b: .word 8082
    """
)

def dump_asm_to_S_file(val_lst, filename="asm.S"):
    import os
    if os.path.isfile(filename):
        # raise ValueError(f"Error: File {filename} already exists!")
        os.remove(filename)
    with open(filename, "w") as f:
        for instr in val_lst:
            assert type(instr) == int
        f.writelines("\n /* This file was dumped automatically */\n")
        f.writelines([f".word {hex(instr)} /* {format(instr, '032b')} */\n" for instr in val_lst])
    print(f"OK, file '{filename}'' dumped!")

    import subprocess

    obj_filename = filename.split('.')[-2] + ".o"
    subprocess.getoutput(f"riscv-none-embed-gcc -c {filename} -o {obj_filename}")
    output = subprocess.getoutput(f"riscv-none-embed-objdump -d {obj_filename}")
    print(output)

# https://stackoverflow.com/a/312464
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# returns bytearray with asm.
def dump_asm(string):
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
    print(code)

    code = [int.from_bytes(x, 'little') for x in chunks(code, 4)] # 4 byte chunks
    print([hex(instr) for instr in code])
    print(code)
    for i, instr in enumerate(code, 1):
        print(f"{i}: {format(instr, '032b')} ")

    print("====================================")
    for i, instr in enumerate(code, 1):
        shift = 32
        l = [7, 5, 5, 3, 5, 7] # funct7, r2, r1, funct3, rd, opcode
        print(f"{i}: ", end='')
        for s in l:
            shift -= s
            f = f"{format(instr >> shift & (2**s-1), f'0{s}b')}"
            print(f"{f},", end='')
        print("")

    dump_asm_to_S_file(code)
    return code

if __name__ == "__main__":
    dump_asm(source_file)

