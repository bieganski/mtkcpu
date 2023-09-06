from typing import Optional
from mtkcpu.cpu.priv_isa import PrivModeBits
from amaranth.sim import Simulator
from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.utils.common import EBRMemConfig, CODE_START_ADDR


def basic_vm_test():
	cpu = MtkCpu(
		mem_config=EBRMemConfig(
			mem_size_words=0x123,
    		mem_content_words=None, # Optional[List[int]]
    		mem_addr=CODE_START_ADDR,
    		simulate=True,
		)
	)

	def wait_decode() -> int: # returns pc of instr being decoded
		while True:
			if (yield cpu.main_fsm.ongoing("DECODE")):
				return (yield cpu.pc)
			yield

	def wait_pc(target_pc : int, instr_limit: Optional[int]=None):
		import logging
		logging.info(f"== waiting for pc {target_pc}")
		miss = 0
		while True:
			pc = wait_decode()
			logging.info(f"pc: {pc}")
			if pc == target_pc:
				logging(f"pc {target_pc} found")
			else:
				miss += 1
				if miss == instr_limit:
					raise ValueError(f"limit of {instr_limit} instructions exceeded while waiting for {target_pc}")
		
	# TODO test is not finished.
	def main():
		yield cpu.current_priv_mode.eq(PrivModeBits.USER)
		yield cpu.csr_unit.satp.eq(0x8000_0123)
		res = []
		for _ in range (30):
			priv = yield cpu.current_priv_mode
			priv = yield cpu.arbiter.addr_translation_en
			priv = yield cpu.csr_unit.satp.mode
			priv = yield cpu.pc
			res.append(hex(priv))
			yield
		raise ValueError(res)


	sim = Simulator(cpu)
	sim.add_clock(1e-6)
	sim.add_sync_process(main)

	from mtkcpu.utils.tests.sim_tests import get_state_name, find_fsm

	# fsm = find_fsm(cpu.arbiter, "fsm")
	# main_fsm = find_fsm(cpu, "fsm")
	# raise ValueError(fsm)

	traces = [
		sim._fragment.domains["sync"].clk,
		cpu.pc,
		cpu.arbiter.addr_translation_en,
		cpu.arbiter.translation_ack,
		cpu.arbiter.start_translation,
		# fsm.state,
		cpu.arbiter.pe.i,
		cpu.arbiter.pe.o,
		cpu.arbiter.pe.none,
		cpu.csr_unit.satp.mode,
		cpu.csr_unit.satp.ppn,
		cpu.arbiter.first,
		cpu.arbiter.error_code,
		# main_fsm.state
	]

	with sim.write_vcd(f"vm.vcd", "vm.gtkw", traces=traces):
		sim.run()