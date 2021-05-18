import pytest
from mtkcpu.utils.common import START_ADDR
from mtkcpu.tests.utils import MemTestCase, MemTestSourceType, assert_mem_test
from mtkcpu.tests.models import RegistryContents

COMPARE_TESTS = [
    MemTestCase(
        name="simple 'sltiu'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            lui x1, 0xffff
            sltiu x2, x1, 0xffe
        """,
        out_reg=2,
        out_val=1,
        timeout=10,
    ),
    MemTestCase(
        name="simple 'slti'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            lui x1, 0xffff
            slti x3, x1, 0xffe
        """,
        out_reg=3,
        out_val=0,
        timeout=10,
    ),
    MemTestCase(
        name="simple 'sltu'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            sltu x1, x3, x2
        """,
        out_reg=1,
        out_val=1,
        reg_init=RegistryContents(reg=[-i for i in range(32)]),
        timeout=10,
    ),
    MemTestCase(
        name="simple 'slt'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            slt x1, x3, x2
        """,
        out_reg=1,
        out_val=1,
        reg_init=RegistryContents(reg=[-i for i in range(32)]),
        timeout=10,
    ),
]


@pytest.mark.parametrize("test_case", COMPARE_TESTS)
def test_compare(test_case):
    assert_mem_test(test_case)
