from mtkcpu.cpu.priv_isa import *
from mtkcpu.utils.common import MEM_START_ADDR, CODE_START_ADDR
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.utils import (MemTestCase, MemTestSourceType, mem_test)

from mtkcpu.cpu.priv_isa import PrivModeBits, pte_layout, satp_layout
from mtkcpu.units.csr import RegisterResetValue

# page tables phys. addresses must be aligned to 4K == 0x1000 bytes
root_pt_offset = 0x2000
leaf_pt_offset = root_pt_offset + 0x1000

root_pt_addr = MEM_START_ADDR + root_pt_offset
leaf_pt_addr = root_pt_addr + leaf_pt_offset

def get_flat_value_generator(layout):
    return lambda fields: RegisterResetValue.calc_reset_value(fields, layout)

def get_field_values_generator(layout):
    return lambda value: RegisterResetValue.value_to_fields(value, layout)

satp_get_flat_value = get_flat_value_generator(satp_layout)
satp_get_field_values = get_field_values_generator(satp_layout)

pte_get_flat_value = get_flat_value_generator(pte_layout)
pte_get_fields_values = get_field_values_generator(pte_layout)

satp_value = satp_get_flat_value({
    "mode": 1, # enable address translation in user mode
    "ppn": root_pt_addr >> 12,
})

virt_addr_high = 0x111
virt_addr_low = 0x222
virt_addr_offset = 0x1 # is not virtualized
virt_addr = virt_addr_offset + (virt_addr_low << 12) + (virt_addr_high << 22)
usermode_virt_addr =virt_addr
pte_size = 4

hi = lambda x: x >> 22
lo = lambda x: (x >> 12) & ((1 << 10) - 1)
off = lambda x: x & ((1 << 12) - 1)

assert hi(virt_addr) == virt_addr_high
assert lo(virt_addr) == virt_addr_low
assert off(virt_addr) == virt_addr_offset

MMU_TESTS = [
    MemTestCase(
        name="enable address translation, jump to usermode",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                li x1, {satp_value}
                csrw satp, x1
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
            .align 12 # force 0x1000 offset - thus 'usermode' label in known address: MEM_START_ADDR + 0x1000 + 0x4
            .dword 0xdeadbeef
            usermode:
                li x3, 0xabcd
            mmode_trap:
                li x3, 0x1234
        """,
        out_reg=3,
        out_val=0xabcd,
        timeout=150,
        # mepc will be set to 'usermode_virt_addr'.
        # when usermode starts, it's expected to perform address translation
        # and jump to MEM_START_ADDR + 0x1000 + offset (address of symbol 'usermode').
        mem_init=MemoryContents(memory={
            root_pt_offset + pte_size * hi(usermode_virt_addr): pte_get_flat_value({
                "v": 1,
                # {ppn0, ppn1} is a pointer to the next level pte
                "ppn1": hi(leaf_pt_addr),
                "ppn0": lo(leaf_pt_addr),
            }),
            leaf_pt_offset + pte_size * lo(usermode_virt_addr): pte_get_flat_value({
                "v": 1,
                "r": 1,
                "w": 1,
                # {ppn0, ppn1} is a pointer to physical address of a page containing 'usermode' symbol.
                "ppn1": hi(MEM_START_ADDR + 0x1000),
                "ppn0": lo(MEM_START_ADDR + 0x1000),
            }),
        }),
        reg_init=RegistryContents.fill(),
        mem_size_kb=16
    ),
]

import pytest
@pytest.mark.skip
@mem_test(MMU_TESTS)
def test_addr_translation(_):
    pass
