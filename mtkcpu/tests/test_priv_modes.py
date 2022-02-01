from mtkcpu.cpu.priv_isa import *
from mtkcpu.utils.common import CODE_START_ADDR
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.utils import (MemTestCase, MemTestSourceType, mem_test)

from mtkcpu.units.csr_handlers import MISA

from mtkcpu.cpu.priv_isa import PrivModeBits

PRIV_TESTS = [
    MemTestCase(
        name="jump to usermode and inside trap read mstatus.mpp",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                // CPU boots in machine mode.
                la x5, usermode
                csrw mepc, x5
                // set 'previous priv.' mstatus's field to user mode 
                li x4, {PrivModeBits.USER}
                slli x4, x4, {get_layout_field_offset(mstatus_layout, 'mpp')}
                csrw mstatus, x4
                // set machine mode trap
                la x4, mmode_trap
                csrw mtvec, x4
                // jump to user mode
                mret
            loop:
                j loop
            usermode:
                .dword 0x0 // illegal insn, trap mmode 
                j loop
            mmode_trap:
                csrr x3, mstatus
        """,
        out_reg=3,
        out_val=lambda x : x & (1 << get_layout_field_offset(mstatus_layout, 'mpp')) == PrivModeBits.USER,
        timeout=150,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.fill(),
    ),

    MemTestCase(
        name="usermode read csr issues illegal insn exception",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                // CPU boots in machine mode.
                la x5, usermode
                csrw mepc, x5
                // set 'previous priv.' mstatus's field to user mode 
                li x4, {PrivModeBits.USER}
                slli x4, x4, {get_layout_field_offset(mstatus_layout, 'mpp')}
                csrw mstatus, x4
                // set machine mode trap
                la x4, mmode_trap
                csrw mtvec, x4
                // jump to user mode
                mret
            loop:
                j loop
            usermode:
                csrr x3, mtvec
                j loop
            mmode_trap:
                csrr x3, mcause
        """,
        out_reg=3,
        out_val=TrapCause.ILLEGAL_INSTRUCTION,
        timeout=150,
        mem_init=MemoryContents.empty(),
        reg_init=RegistryContents.fill(),
    ),

]

@mem_test(PRIV_TESTS)
def test_priv_modes(_):
    pass
