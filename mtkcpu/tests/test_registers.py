import pytest
from mtkcpu.utils.tests.utils import MemTestCase, MemTestSourceType, assert_mem_test, mem_test
from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.memory import MemoryContents

REGISTERS_TESTS = [
    MemTestCase(
        name="simple 'add'",
        source_type = MemTestSourceType.TEXT,
        source="""
        .section code
            add x3, x2, x3
            ; lw t0, 0(t1)
            ; li t1, 0xdeadbeef
        """,
        out_reg=3,
        out_val=5,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents(reg=[i for i in range(32)])
    ),
    MemTestCase(
        name="simple 'sub'",
        source_type = MemTestSourceType.TEXT,
        source=
        """
        .section code
            sub x10, x3, x2
        """,
        out_reg=10,
        out_val=1,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents(reg=[i for i in range(32)]),
    ),
    MemTestCase(
        name="simple 'srli'",
        source_type = MemTestSourceType.TEXT,
        source=
        """
        .section code
            srli x10, x11, 2
        """,
        out_reg=10,
        out_val=0b1,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.empty(value=0b111),
    ),
    MemTestCase(
        name="simple 'srl'",
        source_type = MemTestSourceType.TEXT,
        source=
        """
        .section code
            srl x10, x11, x1
        """,
        out_reg=10,
        out_val=0b101,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents(reg=[i for i in range(32)]),
    ),
    MemTestCase(
        name="simple 'slli'",
        source_type = MemTestSourceType.TEXT,
        source=
        """
        .section code
            slli x10, x11, 2
        """,
        out_reg=10,
        out_val=0b11100,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.empty(value=0b111),
    ),
    MemTestCase(
        name="simple 'sll'",
        source_type = MemTestSourceType.TEXT,
        source=
        """
        .section code
            sll x10, x11, x1
        """,
        out_reg=10,
        out_val=0b10110,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents(reg=[i for i in range(32)]),
    ),
    MemTestCase(
        name="simple 'sra'",
        source_type = MemTestSourceType.TEXT,
        source=
        """
        .section code
            sra x10, x11, x1
        """,
        out_reg=10,
        out_val=0b101,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents(reg=[i for i in range(32)]),
    ),
    MemTestCase(
        name="simple 'srai'",
        source_type = MemTestSourceType.TEXT,
        source=
        """
        .section code
            srai x10, x11, 2
        """,
        out_reg=10,
        out_val=0b1,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.empty(value=0b111),
    ),
    MemTestCase(
        # calculated by https://www.cs.cornell.edu/courses/cs3410/2019sp/riscv/interpreter/
        name="fully functional 'srai'",
        source_type = MemTestSourceType.TEXT,
        source=
        """
        .section code
            srai x2, x1, 4
        """,
        out_reg=2,
        out_val=-7 & 0xFFFFFFFF, # ah, that python infinite-bit representation...
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.empty(value=-100),
    ),
    MemTestCase(
        name="fully functional 'sra'",
        source_type = MemTestSourceType.TEXT,
        source=
        """
        .section code
            sra x2, x2, x1
        """,
        out_reg=2,
        out_val=0b11000000000000000000000000000000,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents(reg=[0, 1, 0x80000000])
    ),
    MemTestCase(
        name="simple 'or'",
        source_type = MemTestSourceType.TEXT,
        source=
        f"""
        .section code
            or x2, x{0b00001}, x{0b00111}
        """,
        out_reg=2,
        out_val=0b111,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents(reg=[i for i in range(32)]),
    ),
    MemTestCase(
        name="simple 'and'",
        source_type = MemTestSourceType.TEXT,
        source=
        f"""
        .section code
            and x2, x{0b10011}, x{0b00111}
        """,
        out_reg=2,
        out_val=0b11,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents(reg=[i for i in range(32)]),
    ),
    MemTestCase(
        name="simple 'xor'",
        source_type = MemTestSourceType.TEXT,
        source=
        f"""
        .section code
            xor x2, x{0b10101}, x{0b1111}
        """,
        out_reg=2,
        out_val=0b11010,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents(reg=[i for i in range(32)]),
    ),
    MemTestCase(
        name="simple 'xori'",
        source_type = MemTestSourceType.TEXT,
        source=
        f"""
        .section code
            xori x5, x{0b11111}, {0b01010}
        """,
        out_reg=5,
        out_val=0b10101,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents(reg=[i for i in range(32)]),
    ),
    MemTestCase(
        name="simple 'ori'",
        source_type = MemTestSourceType.TEXT,
        source=
        f"""
        .section code
            ori x2, x{0b00001}, {0b00111}
        """,
        out_reg=2,
        out_val=0b111,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents(reg=[i for i in range(32)]),
    ),
    MemTestCase(
        name="simple 'andi'",
        source_type = MemTestSourceType.TEXT,
        source=
        f"""
        .section code
            andi x2, x{0b10011}, {0b00111}
        """,
        out_reg=2,
        out_val=0b11,
        timeout=5,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents(reg=[i for i in range(32)]),
    ),
]


@mem_test(REGISTERS_TESTS)
def test_registers(_):
    pass
