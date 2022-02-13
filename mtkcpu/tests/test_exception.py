from mtkcpu.cpu.priv_isa import *
from mtkcpu.utils.common import CODE_START_ADDR
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.utils import (MemTestCase, MemTestSourceType, mem_test)

EXCEPTION_TESTS = [
    MemTestCase(
        name="[no-translation mode] instruction fetch access fault - mcause check",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                la x5, trap
                csrw mtvec, x5
                li x5, {CODE_START_ADDR + 0x0010_0000} // hopefully non-existing address
                jalr x0, x5
            trap:
                csrr x2, mcause
        """,
        out_reg=2,
        out_val=TrapCause.FETCH_ACCESS_FAULT,
        timeout=100,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.empty(),
    ),

    MemTestCase(
        name="[no-translation mode] memory store access fault - mcause check",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                la x5, trap
                csrw mtvec, x5
                li x5, {CODE_START_ADDR + 0x0010_0000} // hopefully non-existing address
                sw x20, 0(x5)
            loop:
                j loop
            trap:
                csrr x2, mcause
        """,
        out_reg=2,
        out_val=TrapCause.STORE_ACCESS_FAULT,
        timeout=100,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.empty(),
    ),

    MemTestCase(
        name="[no-translation mode] memory load access fault - mcause check",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                la x5, trap
                csrw mtvec, x5
                li x5, {CODE_START_ADDR + 0x0010_0000} // hopefully non-existing address
                lw x20, 0(x5)
            loop:
                j loop
            trap:
                csrr x2, mcause
        """,
        out_reg=2,
        out_val=TrapCause.LOAD_ACCESS_FAULT,
        timeout=100,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.empty(),
    ),

    MemTestCase(
        name="mcause illegal instruction",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                la x5, trap
                csrw mtvec, x5
                .dword 0xbaad // invalid instr
                addi x2, x0, 10
            trap:
                csrr x2, mcause
        """,
        out_reg=2,
        out_val=TrapCause.ILLEGAL_INSTRUCTION,
        timeout=100,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.fill(),
    ),

    MemTestCase(
        name="mcause misaligned instruction",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                la x5, trap
                csrw mtvec, x5
                .dword 0x2000ef # eq. to <jal ra,8000000e <start+0xe> >
            # it was hard to force by gcc to emit misaligned label
            #     jal x1, 0x1 # misaligned
            #     .word 0xffff
            # bad_label:
            #     .word 0xffff
            trap:
                csrr x2, mcause
        """,
        out_reg=2,
        out_val=TrapCause.FETCH_MISALIGNED,
        timeout=100,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.fill(),
    ),
]

@mem_test(EXCEPTION_TESTS)
def test_registers(_):
    pass
