from bitstring import Bits

from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.utils import MemTestCase, MemTestSourceType, mem_test
from mtkcpu.utils.common import MEM_START_ADDR

fill_mem_start_addr = RegistryContents.fill(lambda _ : MEM_START_ADDR)


# in some register we keep memory start address,
# fill anothers with constant or identity.
class FillButOneKeepMemory():
    addr_reg_idx = 1

    def __call__(self, val=None) -> RegistryContents:
        id = lambda x : x 
        f = lambda x: val if val else x
        return RegistryContents.fill(lambda x: MEM_START_ADDR if x == __class__.addr_reg_idx else f(x))

fill_but_one = FillButOneKeepMemory()

MEMORY_TESTS = [
    MemTestCase(
        name="simple 'lw'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            lw x11, 0x80(x1)
        """,
        out_reg=11,
        out_val=0xbadbaddd,
        timeout=10,
        reg_init=fill_mem_start_addr,
        mem_init=MemoryContents(memory={0x80: 0xbadbaddd}),
        mem_out=MemoryContents.empty(),  # empty dict means whatever (no memory checks performed)
    ),
    MemTestCase(
        name="simple 'sw'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            sw x11, 0x80(x1)
        """,
        timeout=10,
        reg_init=fill_mem_start_addr,
        mem_out=MemoryContents(memory={0x80: MEM_START_ADDR}),
    ),
    MemTestCase(
        name="simple 'lh'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            lh x5, 0x80(x1)
        """,
        timeout=10,
        out_reg=5,
        out_val=Bits(
            bin=format(0b11111111_11111111_11111111_00000000, "32b")
        ).uint,  # uint because of bus unsigned..
        reg_init=fill_mem_start_addr,
        mem_init=MemoryContents(
            memory={
                0x80: Bits(
                    bin=format(0b11111111_00000000_11111111_00000000, "32b")
                ).int
            }
        ),
    ),
    MemTestCase(
        name="simple 'lhu'",
        source_type=MemTestSourceType.TEXT,
        source=f"""
        .section code
            lhu x5, 0x20(x{fill_but_one.addr_reg_idx})
        """,
        timeout=10,
        out_reg=5,
        out_val=0b11111111_00000000,
        reg_init=fill_but_one(),
        mem_init=MemoryContents(
            memory={
                0x20: Bits(
                    bin=format(0b11111111_00000000_11111111_00000000, "32b")
                ).int
            }
        ),
    ),
    MemTestCase(
        name="simple 'lb'",
        source_type=MemTestSourceType.TEXT,
        source=f"""
        .section code
            lb x5, 0x20(x{fill_but_one.addr_reg_idx})
        """,
        timeout=10,
        out_reg=5,
        reg_init=fill_but_one(),
        out_val=-3,
        mem_init=MemoryContents(memory={0x20: -3}),
    ),
    MemTestCase(
        name="sign-extend 'lb'",
        source_type=MemTestSourceType.TEXT,
        source=f"""
        .section code
            lb x5, 0x20(x{fill_but_one.addr_reg_idx})
        """,
        timeout=10,
        out_reg=5,
        reg_init=fill_but_one(),
        out_val=-1,
        mem_init=MemoryContents(memory={0x20: 0xffff_ffff}),
    ),
    MemTestCase(
        name="simple 'lbu'",
        source_type=MemTestSourceType.TEXT,
        source=f"""
        .section code
            lbu x5, 0x20(x{fill_but_one.addr_reg_idx})
        """,
        timeout=10,
        out_reg=5,
        out_val=5,
        reg_init=fill_but_one(),
        mem_init=MemoryContents(memory={0x20: 5}),
    ),
    MemTestCase(
        name="non-aligned 'lbu'",
        source_type=MemTestSourceType.TEXT,
        source=f"""
        .section code
            lbu x5, 0x21(x{fill_but_one.addr_reg_idx})
        """,
        timeout=10,
        out_reg=5,
        out_val=0xbe,
        reg_init=fill_but_one(),
        mem_init=MemoryContents(memory={0x20: 0xdeadbeef}),
    ),
    # TODO tu jestem
    # MemTestCase(
    #     name="simple 'sh'",
    #     source_type=MemTestSourceType.TEXT,
    #     source=f"""
    #     .section code
    #         lui x5, 0xaabbf
    #         addi x5, x5, 0x01cd
    #         sh x5, 0x10(x{fill_but_one.addr_reg_idx})
    #     """,
    #     timeout=10,
    #     reg_init=fill_but_one(),
    #     mem_init=MemoryContents(memory={0x10: 0}),
    #     mem_out=MemoryContents(memory={0x10: 0}),
    # ),
    MemTestCase(
        name="negative 'sh'",
        source_type=MemTestSourceType.TEXT,
        source=f"""
        .section code
            sh x5, 0x10(x{fill_but_one.addr_reg_idx})
        """,
        timeout=10,
        reg_init=fill_but_one(-5),
        mem_out=MemoryContents(memory={0x10: Bits(int=-5, length=16).uint}),
    ),

    MemTestCase(
        name="overwrite 'sb'",
        source_type=MemTestSourceType.TEXT,
        source=f"""
        .section code
            sb x5, 0x10(x{fill_but_one.addr_reg_idx})
        """,
        timeout=10,
        reg_init=fill_but_one(0xAA),
        mem_init=MemoryContents(memory={0x10: 0xDEADBEEF}),
        mem_out=MemoryContents(memory={0x10: 0xDEADBEAA}),
    ),
    MemTestCase(
        name="overwrite 'sh'",
        source_type=MemTestSourceType.TEXT,
        source=f"""
        .section code
            sh x5, 0x10(x{fill_but_one.addr_reg_idx})
        """,
        timeout=10,
        reg_init=fill_but_one(0xAAAA),
        mem_init=MemoryContents(memory={0x10: 0xDEADBEEF}),
        mem_out=MemoryContents(memory={0x10: 0xDEADAAAA}),
    ),
    MemTestCase(
        name="overwrite 'sw'",
        source_type=MemTestSourceType.TEXT,
        source=f"""
        .section code
            sw x5, 0xcc(x{fill_but_one.addr_reg_idx})
        """,
        timeout=10,
        reg_init=fill_but_one(0xAAAA),
        mem_init=MemoryContents(memory={0xcc: 0xDEADBEEF}),
        mem_out=MemoryContents(memory={0xcc: 0xAAAA}),
    ),
]

@mem_test(MEMORY_TESTS)
def test_memory(_):
    pass
