import pytest
from mtkcpu.utils.common import START_ADDR
from mtkcpu.tests.utils import MemTestCase, MemTestSourceType, assert_mem_test
from mtkcpu.tests.models import RegistryContents, MemoryContents
from bitstring import Bits

MEMORY_TESTS = [
    MemTestCase(
        name="simple 'lw'",
        source_type=MemTestSourceType.TEXT,
        source=
        """
        .section code
            addi x10, x0, 0xde
            lw x11, 0xde(x0)
        """,
        out_reg=11,
        out_val=0xdeadbeef,
        timeout=10,
        mem_init=MemoryContents(memory={0xde: 0xdeadbeef}),
        mem_out=MemoryContents.empty() # empty dict means whatever (no memory checks performed)
    ),
    MemTestCase(
        name="simple 'sw'",
        source_type=MemTestSourceType.TEXT,
        source=
        """
        .section code
            sw x11, 0xaa(x0)
        """,
        timeout=10,
        reg_init=RegistryContents(reg=[i for i in range(32)]),
        mem_out=MemoryContents(memory={0xaa: 11}),
    ),
    MemTestCase(
        name="simple 'lh'",
        source_type=MemTestSourceType.TEXT,
        source=
        """
        .section code
            lh x5, 0xaa(x1)
        """,
        timeout=10,
        out_reg=5,
        out_val=Bits(bin=format(0b11111111_11111111_11111111_00000000, '32b')).uint, # uint because of bus unsigned..
        reg_init=RegistryContents(reg=[i for i in range(32)]),
        mem_init=MemoryContents(memory={0xab: Bits(bin=format(0b11111111_00000000_11111111_00000000, '32b')).int}),
    ),
    MemTestCase(
        name="simple 'lhu'",
        source_type=MemTestSourceType.TEXT,
        source=
        """
        .section code
            lhu x5, 0(x0)
        """,
        timeout=10,
        out_reg=5,
        out_val=0b11111111_00000000,
        mem_init=MemoryContents(memory={0x0: Bits(bin=format(0b11111111_00000000_11111111_00000000, '32b')).int}),
    ),
    MemTestCase(
        name="simple 'lb'",
        source_type=MemTestSourceType.TEXT,
        source=
        """
        .section code
            lb x5, 0(x0)
        """,
        timeout=10,
        out_reg=5,
        out_val=0b11111101, # TODO fix that unsigned bus.
        mem_init=MemoryContents(memory={0x0: -3}),
    ),
    MemTestCase(
        name="simple 'lbu'",
        source_type=MemTestSourceType.TEXT,
        source=
        """
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
        source=
        """
        .section code
            sh x5, 0(x0)
        """,
        timeout=10,
        reg_init=RegistryContents(reg=[i for i in range(32)]),
        mem_init=MemoryContents(memory={0x0: 5}),
        mem_out=MemoryContents(memory={0x0: 5}),
    ),
    MemTestCase(
        name="negative 'sh'",
        source_type=MemTestSourceType.TEXT,
        source=
        """
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
        source=
        """
        .section code
            sb x5, 0(x1)
        """,
        timeout=10,
        reg_init=RegistryContents.empty(value=0xaa),
        mem_out=MemoryContents(memory={0xaa: 0xaa}),
    ),
    MemTestCase(
        name="overwrite 'sb'",
        source_type=MemTestSourceType.TEXT,
        source=
        """
        .section code
            sb x5, 0(x1)
        """,
        timeout=10,
        reg_init=RegistryContents.empty(value=0xaa),
        mem_init=MemoryContents(memory={0xaa: 0xdeadbeef}),
        mem_out=MemoryContents(memory={0xaa: 0xdeadbeaa}),
    ),
    MemTestCase(
        name="overwrite 'sh'",
        source_type=MemTestSourceType.TEXT,
        source=
        """
        .section code
            sh x5, 0xbb(x0)
        """,
        timeout=10,
        reg_init=RegistryContents.empty(value=0xaaaa),
        mem_init=MemoryContents(memory={0xbb: 0xdeadbeef}),
        mem_out=MemoryContents(memory={0xbb: 0xdeadaaaa}),
    ),
    MemTestCase(    
        name="overwrite 'sw'",
        source_type=MemTestSourceType.TEXT,
        source=
        """
        .section code
            sw x5, 0xbb(x0)
        """,
        timeout=10,
        reg_init=RegistryContents.empty(value=0xaaaa),
        mem_init=MemoryContents(memory={0xbb: 0xdeadbeef}),
        mem_out=MemoryContents(memory={0xbb: 0xaaaa}),
    ),
]


@pytest.mark.parametrize("test_case", MEMORY_TESTS)
def test_memory(test_case):
    assert_mem_test(test_case)
