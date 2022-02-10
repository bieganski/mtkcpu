#!/usr/bin/env python3

from dataclasses import dataclass
from typing import Optional, List

from wasmtime import Val


@dataclass
class SATP:
	asid : int 		# 9
	ppn : int  		# 22
	mode : int 		# 1

@dataclass
class VIRT_ADDR:
	vpn : List[int] # each of size 10
	offset : int 	# 12

# @dataclass
# class PHYS_ADDR:
# 	ppn1 : int 		# 12
# 	ppn0 : int 		# 10
# 	offset : int 	# 12


@dataclass
class PTE:
	ppn1 : int		# 12
	ppn0 : int		# 10
	rsw  : int		# 2
	d : int # dirty
	a : int # accessed
	g : int # global
	u : int # user
	x : int
	w : int
	r : int
	v : int # valid

	def is_leaf(self):
		return not (self.r or self.x)

def get_phys(addr: int) -> int:
	pass

@dataclass
class CPU:
	is_machine : bool

# returns phys addr of page, or None if __?__
def _page_walk(root_pt_phys_addr : int, req_virt_addr: VIRT_ADDR, i: int) -> int:
	pte_size = 4
	pte_phys_addr = root_pt_phys_addr + req_virt_addr.vpn[i] * pte_size
	pte : PTE = get_phys(pte_phys_addr)

	cpu : CPU = 1
	is_store : bool = False

	if not pte.v:
		raise ValueError("CORRESPONDING PAGE FAULT")
	if pte.w and not pte.r:
		raise ValueError("CORRESPONDING PAGE FAULT")
	
	if pte.is_leaf():
		# step 5
		if pte.u: # permission check
			if cpu.is_machine:
				raise ValueError("CORRESPONDING PAGE FAULT")
		else: # permission check
			if not cpu.is_machine:
				raise ValueError("CORRESPONDING PAGE FAULT")
		if pte.a == 0 or (is_store and pte.d == 0):
			raise ValueError("CORRESPONDING PAGE FAULT")
		if i > 0:
			pte.ppn0
			if i == 1 and pte.ppn0 != 0:
				# misaligned superpage
				raise ValueError("CORRESPONDING PAGE FAULT")
		# translation finished, TODO
		# remember to trim 2 upper bits, or maybe it will do automatically?
		# below works for both 4KB and 4MB pages
		res = pte.ppn1
		res <<= 10
		res |= pte.ppn0
		res <<= 12
		res |= (req_virt_addr & ((1 << 12) - 1))
		return res
	
	else:
		# not leaf
		if i == 0:
			raise ValueError("CORRESPONDING PAGE FAULT")
		new_addr = pte.ppn1
		new_addr <<= 10
		new_addr |= pte.ppn0
		new_addr <<= 12
		return _page_walk(new_addr, req_virt_addr, i - 1)



def page_walk(req_addr : int) -> Optional[int]:
	satp : SATP = 1
	sv32_i = 1
	
	if satp.mode == 1:
		# 22 bits, + 12
		req_offset = req_addr & ((1 << 12) - 1)
		root_pt_phys_addr = satp.ppn << 12
		phys_addr = _page_walk(root_pt_phys_addr, req_addr, i=sv32_i) + req_offset
		return get_phys(phys_addr)
	else:
		return get_phys(req_addr)
	