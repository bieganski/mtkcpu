import io
import os
from typing import List, Union, Generator
import subprocess

from ppci.api import asm, link


def dump_asm_to_S_file(
    val_lst: List[int],
    filename: str = "asm.S",
    verbose: bool = False,
):
    if os.path.isfile(filename):
        os.remove(filename)
    with open(filename, "w") as f:
        for instr in val_lst:
            assert type(instr) == int
        f.writelines("\n /* This file was dumped automatically */\n")
        f.writelines(
            [
                f".word {hex(instr)} /* {format(instr, '032b')} */\n"
                for instr in val_lst
            ]
        )
    LOG(f"OK, file '{filename}'' dumped!", verbose=verbose)

    obj_filename = f"{filename.split('.')[-2]}.o"
    subprocess.getoutput(
        f"riscv-none-embed-gcc -c {filename} -o {obj_filename}"
    )
    output = subprocess.getoutput(
        f"riscv-none-embed-objdump -d {obj_filename}"
    )
    LOG(output, verbose=verbose)


# https://stackoverflow.com/a/312464
def chunks(lst: bytes, n: int) -> Generator[bytes, None, None]:
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def LOG(*args, **kwargs):
    # if 'verbose' not in kwargs or
    if not kwargs["verbose"]:
        return
    kwargs.pop("verbose")
    print(*args, **kwargs)


# returns bytearray with asm.
def dump_asm(
    code_input: str,
    verbose: bool = False,
) -> List[int]:

    obj = asm(io.StringIO(code_input), "riscv") # NOQA
    obj = link([obj])

    code = obj.get_section("code").data
    code = bytes_to_u32_arr(code)
    dump_instrs(code)
    dump_asm_to_S_file(code, verbose=verbose)
    return code


def bytes_to_u32_arr(raw: bytes) -> List[int]:
    return [
        int.from_bytes(x, "little") for x in chunks(raw, 4)
    ]  # 4 byte chunks


def dump_instrs(u32_arr: List[int]):
    verbose = True
    code = u32_arr
    LOG(code, verbose=verbose)

    LOG([hex(instr) for instr in code], verbose=verbose)
    LOG(code, verbose=verbose)
    for i, instr in enumerate(code, 1):
        from riscvmodel.code import decode
        LOG(f"{hex(instr)}: {decode(instr)}", verbose=verbose)
        LOG(f"{i}: {format(instr, '032b')} ", verbose=verbose)

    LOG("====================================", verbose=verbose)
    for i, instr in enumerate(code, 1):
        shift = 32
        LOG(f"{i}: ", end="", verbose=verbose)
        for s in [7, 5, 5, 3, 5, 7]:  # funct7, r2, r1, funct3, rd, opcode
            shift -= s
            f = f"{format(instr >> shift & (2**s-1), f'0{s}b')}"
            LOG(f"{f},", end="", verbose=verbose)
        LOG("", verbose=verbose)


if __name__ == "__main__":
    dump_asm("""
    .section code
        jalr x10, x8, 0x0
    """, verbose=True)
