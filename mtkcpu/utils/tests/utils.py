from __future__ import annotations
from dataclasses import dataclass
from mtkcpu.cpu.cpu import MtkCpu
from typing import Optional
from itertools import count
from mtkcpu.asm.asm_dump import dump_asm
from mtkcpu.utils.common import START_ADDR
from enum import Enum, unique

from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.utils.tests.sim_tests import get_sim_memory_test, get_sim_register_test

from io import StringIO

@unique
class MemTestSourceType(str, Enum):
    TEXT = "text"
    RAW = "raw"
    ELF = "elf"


@dataclass(frozen=True)
class MemTestCase:
    name: str
    source: str
    source_type: MemTestSourceType
    out_reg: Optional[int] = None
    out_val: Optional[int] = None
    mem_out: Optional[MemoryContents] = None
    timeout: Optional[int] = None
    mem_init: Optional[MemoryContents] = None
    reg_init: Optional[RegistryContents] = None


def reg_test(
    name: str,
    timeout_cycles: Optional[int],
    reg_num: int,
    expected_val: Optional[int],
    expected_mem: Optional[MemoryContents],
    reg_init: RegistryContents,
    mem_dict: Optional[MemoryContents],
    verbose: bool = False,
):
    from nmigen.back.pysim import Simulator
    cpu = MtkCpu(reg_init=reg_init.reg)
    sim = Simulator(cpu)
    sim.add_clock(1e-6)

    assert ((reg_num is None and expected_val is None) or (reg_num is not None and expected_val is not None))

    sim.add_sync_process(get_sim_memory_test(cpu=cpu, mem_dict=mem_dict))
    sim.add_sync_process(get_sim_register_test(name=name, cpu=cpu, reg_num=reg_num, expected_val=expected_val, timeout_cycles=timeout_cycles))
    with sim.write_vcd("cpu.vcd"):
        sim.run()

    if expected_mem is not None:
        mem_dict.assert_equality(expected_mem)


def get_code_mem(case: MemTestCase) -> MemoryContents:
    if case.source_type == MemTestSourceType.TEXT:
        source_file = StringIO(case.source)
        code = dump_asm(source_file, verbose=False)
        return MemoryContents(
            memory=dict(zip(count(START_ADDR, 4), code)),
        )
    else:
        raise KeyError(f"Unsupported MemTestSourceType in MemTestCase: {case.source_type}")


def assert_mem_test(case: MemTestCase):
    name = case.name
    reg_init = case.reg_init or RegistryContents.empty()
    mem_init = case.mem_init or MemoryContents.empty()

    program = get_code_mem(case).patch(mem_init, can_overlap=False)
    reg_test(
        name=name,
        timeout_cycles=case.timeout,
        reg_num=case.out_reg,
        expected_val=case.out_val,
        expected_mem=case.mem_out,
        reg_init=reg_init,
        mem_dict=program,
        verbose=True)
