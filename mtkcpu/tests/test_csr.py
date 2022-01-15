from mtkcpu.cpu.priv_isa import Cause
from mtkcpu.utils.common import CODE_START_ADDR
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.utils import (MemTestCase, MemTestSourceType, mem_test)

from mtkcpu.units.csr_handlers import MISA

CSR_TESTS = [
    MemTestCase(
        name="read 'misa' CPU architecture with supported extensions",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                csrr x3, misa
        """,
        out_reg=3,
        out_val=MISA().reset_value,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.fill(),
    ),

    MemTestCase(
        name="misa is WARL",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                csrrw x1, misa, x3
                csrr x2, misa
        """,
        out_reg=2,
        out_val=MISA().reset_value,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.fill(),
    ),

    MemTestCase(
        name="trap 'mtvec'",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                la x5, trap
                csrw mtvec, x5
                .word 0x0000 // invalid instr
                addi x2, x0, 10
            trap:
                addi x2, x0, 20
            // TODO implement mret
        """,
        out_reg=2,
        out_val=20,
        timeout=100,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.fill(),
    ),

    MemTestCase(
        name="trap check mtval",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                la x5, trap
                csrw mtvec, x5
                .word 0xbaad // invalid instr
                addi x2, x0, 10
            trap:
                csrr x2, mtval
        """,
        out_reg=2,
        out_val=0xbaad,
        timeout=100,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.fill(),
    ),

    MemTestCase(
        name="trap check mepc",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                la x5, trap
                csrw mtvec, x5
                .word 0xbaad // invalid instr
                addi x2, x0, 10
            trap:
                csrr x2, mepc
        """,
        out_reg=2,
        out_val=CODE_START_ADDR + 3*4,
        timeout=100,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.fill(),
    ),

    MemTestCase(
        name="mscratch write read",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                csrw mscratch, x6 // not needed: only make sure it won't trigger write to register x6
                li x5, 0xdeadbeef
                csrw mscratch, x5
                csrr x6, mscratch
        """,
        out_reg=6,
        out_val=0xdeadbeef,
        timeout=100,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.empty(value=1),
    ),

    MemTestCase(
        name="mhartid read zero",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                csrr x5, mhartid
        """,
        out_reg=5,
        out_val=0,
        timeout=100,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.empty(value=1),
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
        out_val=Cause.ILLEGAL_INSTRUCTION,
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
        out_val=Cause.FETCH_MISALIGNED,
        timeout=100,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.fill(),
    ),
]


# TODO:
# * make sure that mcause etc. should not be cleared
@mem_test(CSR_TESTS)
def test_registers(_):
    pass
