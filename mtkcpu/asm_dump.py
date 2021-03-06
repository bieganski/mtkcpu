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
        ; li t1, 0xdeadbeef
    """
)

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
    print(obj.sections)
    code = obj.get_section('code').data
    # from pprint import pprint
    # pprint(dir(obj))
    # s = obj.get_symbol('printf')
    # print(dir(s))
    print(code)

    code = [int.from_bytes(x, 'little') for x in chunks(code, 4)] # 4 byte chunks
    print(code)
    for i, instr in enumerate(code):
        print(f"{i}: {format(instr, '032b')} ")
    return code

if __name__ == "__main__":
    dump_asm(source_file)

