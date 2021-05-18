import pytest
from mtkcpu.utils.common import START_ADDR
from mtkcpu.utils.tests.utils import MemTestCase, MemTestSourceType, mem_test
from mtkcpu.utils.tests.registers import RegistryContents
from bitstring import Bits

UPPER_TESTS = [
    MemTestCase(
        name="simple 'lui'",
        source_type=MemTestSourceType.TEXT,
        source=
        """
        .section code
            lui x1, 0xfffff
        """,
        out_reg=1,
        out_val=Bits(uint=0xfffff000, length=32).uint,
        timeout=10,
    ),
    MemTestCase(
        name="overwrite 'lui'",
        source_type=MemTestSourceType.TEXT,
        source=
        """
        .section code
            lui x1, 0xfffff
        """,
        out_reg=1,
        out_val=Bits(uint=0xfffff0aa, length=32).uint,
        reg_init=RegistryContents.empty(value=0xaa),
        timeout=10,
    ),
    MemTestCase(
        name="simple 'auipc'",
        source_type=MemTestSourceType.TEXT,
        source=
        """
        .section code
            auipc x1, 0xaa
        """,
        out_reg=1,
        out_val=START_ADDR + (0xaa << 12),
        timeout=10,
    ),
]


@mem_test(UPPER_TESTS)
def test_upper(_):
    pass
