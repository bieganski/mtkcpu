from bitstring import Bits

from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.utils import MemTestCase, MemTestSourceType, mem_test

MEMORY_TESTS = [
    MemTestCase(
        name="simple 'lw'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            addi x10, x0, 0xde
            lw x11, 0xde(x0)
        """,
        out_reg=11,
        out_val=0xDEADBEEF,
        timeout=10,
        mem_init=MemoryContents(memory={0xDE: 0xDEADBEEF}),
        mem_out=MemoryContents.empty(),  # empty dict means whatever (no memory checks performed)
    ),
    MemTestCase(
        name="simple 'sw'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            sw x11, 0xaa(x0)
        """,
        timeout=10,
        reg_init=RegistryContents.fill(),
        mem_out=MemoryContents(memory={0xAA: 11}),
    ),
    MemTestCase(
        name="simple 'lh'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            lh x5, 0xaa(x1)
        """,
        timeout=10,
        out_reg=5,
        out_val=Bits(
            bin=format(0b11111111_11111111_11111111_00000000, "32b")
        ).uint,  # uint because of bus unsigned..
        reg_init=RegistryContents.fill(),
        mem_init=MemoryContents(
            memory={
                0xAB: Bits(
                    bin=format(0b11111111_00000000_11111111_00000000, "32b")
                ).int
            }
        ),
    ),
    MemTestCase(
        name="simple 'lhu'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            lhu x5, 0(x0)
        """,
        timeout=10,
        out_reg=5,
        out_val=0b11111111_00000000,
        mem_init=MemoryContents(
            memory={
                0x0: Bits(
                    bin=format(0b11111111_00000000_11111111_00000000, "32b")
                ).int
            }
        ),
    ),
    MemTestCase(
        name="simple 'lb'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            lb x5, 0(x0)
        """,
        timeout=10,
        out_reg=5,
        out_val=0b11111101,  # TODO fix that unsigned bus.
        mem_init=MemoryContents(memory={0x0: -3}),
    ),
    MemTestCase(
        name="simple 'lbu'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            lbu x5, 0(x0)
        """,
        timeout=10,
        out_reg=5,
        out_val=5,
        mem_init=MemoryContents(memory={0x0: 5}),
    ),
    MemTestCase(
        name="simple 'sh'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            sh x5, 0(x0)
        """,
        timeout=10,
        reg_init=RegistryContents.fill(),
        mem_init=MemoryContents(memory={0x0: 5}),
        mem_out=MemoryContents(memory={0x0: 5}),
    ),
    MemTestCase(
        name="negative 'sh'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            sh x5, 0(x0)
        """,
        timeout=10,
        reg_init=RegistryContents.empty(value=-5),
        mem_out=MemoryContents(memory={0x0: Bits(int=-5, length=16).uint}),
    ),
    MemTestCase(
        name="simple 'sb'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            sb x5, 0(x1)
        """,
        timeout=10,
        reg_init=RegistryContents.empty(value=0xAA),
        mem_out=MemoryContents(memory={0xAA: 0xAA}),
    ),
    MemTestCase(
        name="overwrite 'sb'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            sb x5, 0(x1)
        """,
        timeout=10,
        reg_init=RegistryContents.empty(value=0xAA),
        mem_init=MemoryContents(memory={0xAA: 0xDEADBEEF}),
        mem_out=MemoryContents(memory={0xAA: 0xDEADBEAA}),
    ),
    MemTestCase(
        name="overwrite 'sh'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            sh x5, 0xbb(x0)
        """,
        timeout=10,
        reg_init=RegistryContents.empty(value=0xAAAA),
        mem_init=MemoryContents(memory={0xBB: 0xDEADBEEF}),
        mem_out=MemoryContents(memory={0xBB: 0xDEADAAAA}),
    ),
    MemTestCase(
        name="overwrite 'sw'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            sw x5, 0xbb(x0)
        """,
        timeout=10,
        reg_init=RegistryContents.empty(value=0xAAAA),
        mem_init=MemoryContents(memory={0xBB: 0xDEADBEEF}),
        mem_out=MemoryContents(memory={0xBB: 0xAAAA}),
    ),
]


@mem_test(MEMORY_TESTS)
def test_memory(_):
    pass
