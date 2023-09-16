from mtkcpu.cpu.priv_isa import *
from mtkcpu.utils.common import MEM_START_ADDR, CODE_START_ADDR
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.utils import (MemTestCase, MemTestSourceType, mem_test)
from mtkcpu.units.csr.types import MSTATUS_Layout, SATP_Layout

from amaranth import Signal

# page tables phys. addresses must be aligned to 4K == 0x1000 bytes
root_pt_offset = 0x2000
leaf_pt_offset = root_pt_offset + 0x1000

root_pt_addr = MEM_START_ADDR + root_pt_offset
leaf_pt_addr = MEM_START_ADDR + leaf_pt_offset

satp_value = SATP_Layout.const({
    "mode": 1, # enable address translation in user mode
    "ppn": root_pt_addr >> 12,
}).value

pte_const = lambda fields: PTE_Layout.const(fields).value

# https://github.com/amaranth-lang/amaranth/issues/786
mpp_offset_in_MSTATUS = MSTATUS_Layout(Signal(32))._View__layout._fields["mpp"].offset

virt_addr_high = 0x111
virt_addr_low = 0x222
virt_addr_vpn = virt_addr_low + (virt_addr_high << 10) # 20 bits at most
usermode_virt_addr_vpn = virt_addr_vpn
pte_size = 4

# below functions apply either to ppn and vpn
hi_pn = lambda x: x >> 10
lo_pn = lambda x: x & ((1 << 10) - 1)

assert hi_pn(virt_addr_vpn) == virt_addr_high
assert lo_pn(virt_addr_vpn) == virt_addr_low

root_page_phys_addr = root_pt_addr + pte_size * hi_pn(usermode_virt_addr_vpn)
leaf_page_phys_addr = leaf_pt_addr + pte_size * lo_pn(usermode_virt_addr_vpn)
# raise ValueError(hex(root_page_phys_addr), hex(leaf_page_phys_addr)) # ('0x80002444', '0x80003888')

usermode_phys_pn = (MEM_START_ADDR + 0x1000) >> 12
MMU_TESTS = [
    MemTestCase(
        name="enable address translation, jump to usermode",
        source_type=MemTestSourceType.RAW,
        source=f"""
            start:
                li x1, {satp_value}
                csrw satp, x1
                // CPU boots in machine mode.
                
                li x4, %lo(usermode)
                lui x5, {usermode_virt_addr_vpn}
                add x5, x5, x4
                csrw mepc, x5

                // set 'previous priv.' mstatus's field to user mode 
                li x4, {PrivModeBits.USER}
                slli x4, x4, {mpp_offset_in_MSTATUS}
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
                addi x3, x0, 10
            mmode_trap:
                addi x3, x0, 20
        """,
        out_reg=3,
        out_val=10,
        timeout=150,
        # mepc will be set to 'usermode_virt_addr'.
        # when usermode starts, it's expected to perform address translation
        # and jump to MEM_START_ADDR + 0x1000 + offset (address of symbol 'usermode').
        mem_init=MemoryContents(memory={
            root_page_phys_addr: pte_const({
                "v": 1,
                # {ppn0, ppn1} is a pointer to the next level pte
                "ppn1": hi_pn(leaf_pt_addr >> 12),
                "ppn0": lo_pn(leaf_pt_addr >> 12),
            }),
            leaf_page_phys_addr: pte_const({
                "v": 1,
                "r": 1,
                "w": 1,
                "a": 1, # don't trap
                "d": 1, # don't trap
                "u": 1, # allow user-mode touch it
                # {ppn0, ppn1} is a pointer to a physical page containing 'usermode' symbol.
                "ppn1": hi_pn(usermode_phys_pn),
                "ppn0": lo_pn(usermode_phys_pn),
            }),
        }),
        shift_mem_content=False, # MEM_START_ADDR was already used to calculate 'root_page_phys_addr'
        reg_init=RegistryContents.fill(),
        mem_size_kb=16
    ),
]


import pytest
# @pytest.mark.skip
@mem_test(MMU_TESTS)
def test_addr_translation(_):
    pass
