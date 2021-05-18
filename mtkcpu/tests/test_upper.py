import pytest
from mtkcpu.utils.common import START_ADDR
from mtkcpu.tests.utils import MemTestCase, MemTestSourceType, assert_mem_test
from mtkcpu.tests.models import RegistryContents, MemoryContents
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


@pytest.mark.parametrize("test_case", UPPER_TESTS)
def test_upper(test_case):
    assert_mem_test(test_case)
