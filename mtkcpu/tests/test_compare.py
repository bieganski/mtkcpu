from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.utils import MemTestCase, MemTestSourceType, mem_test

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
        reg_init=RegistryContents.fill(lambda i: -i),
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
        reg_init=RegistryContents.fill(lambda i: -i),
        timeout=10,
    ),
]


@mem_test(COMPARE_TESTS)
def test_compare(_):
    pass
