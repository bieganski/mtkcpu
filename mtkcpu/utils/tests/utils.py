from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from io import StringIO
from itertools import count
from typing import List, Optional

from nmigen.hdl.ast import Signal, Value

import pytest

from mtkcpu.asm.asm_dump import dump_asm
from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.utils.common import START_ADDR
from mtkcpu.utils.decorators import parametrized, rename
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.sim_tests import (get_sim_memory_test,
                                          get_sim_register_test,
                                          get_sim_jtag_test)
from mtkcpu.units.debug.jtag import JtagIR
from mtkcpu.units.debug.top import DMIReg

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


@dataclass(frozen=True)
class JtagTestCase:
    pass


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

    assert (reg_num is None and expected_val is None) or (
        reg_num is not None and expected_val is not None
    )

    sim.add_sync_process(get_sim_memory_test(cpu=cpu, mem_dict=mem_dict))
    sim.add_sync_process(
        get_sim_register_test(
            name=name,
            cpu=cpu,
            reg_num=reg_num,
            expected_val=expected_val,
            timeout_cycles=timeout_cycles,
        )
    )
    with sim.write_vcd("cpu.vcd"):
        sim.run()

    if expected_mem is not None:
        mem_dict.assert_equality(expected_mem)


def get_code_mem(case: MemTestCase) -> MemoryContents:
    if case.source_type == MemTestSourceType.TEXT:
        code = dump_asm(case.source, verbose=False)
        return MemoryContents(
            memory=dict(zip(count(START_ADDR, 4), code)),
        )
    else:
        raise KeyError(
            f"Unsupported MemTestSourceType in MemTestCase: {case.source_type}"
        )


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
        verbose=True,
    )

def assert_jtag_test(
    name: str,
    timeout_cycles: Optional[int],
):
    from nmigen.back.pysim import Simulator

    cpu = MtkCpu(reg_init=[0 for _ in range(32)], with_debug=True)
    

    # cursed stuff for retrieving jtag FSM state for 'traces=vcd_traces' variable
    # https://freenode.irclog.whitequark.org/nmigen/2020-07-26#27592720;
    # sim = Simulator(cpu)
    from nmigen.hdl.ir import Fragment
    from nmigen import Signal, ClockDomain

    frag = Fragment.get(cpu, platform=None)
    fsm = frag.find_generated("debug", "jtag", "fsm")
    sim = Simulator(frag)

    # clk = Signal()
    # clk_domain = ClockDomain()
    # clk_domain.clk = clk
    # frag.domains["sync"] = clk_domain

    sim.add_clock(1e-6) # "clk_domain")

    # raise ValueError(f"DOM: {cpu.domains}")

    sim.add_sync_process(
        get_sim_jtag_test(cpu=cpu, timeout_cycles=timeout_cycles, jtag_fsm=fsm)
    )

    jtag_fsm_sig = fsm.state
    main_clk_sig = sim._fragment.domains["sync"].clk


    jtag_loc = cpu.debug.jtag

    dmcontrol_r = cpu.debug.dmi_regs[DMIReg.DMCONTROL].r.fields.values()
    dmcontrol_w = cpu.debug.dmi_regs[DMIReg.DMCONTROL].w.fields.values()

    hartinfo_r = cpu.debug.dmi_regs[DMIReg.HARTINFO].r.fields.values()
    hartinfo_w = cpu.debug.dmi_regs[DMIReg.HARTINFO].w.fields.values()

    abstracts_r = cpu.debug.dmi_regs[DMIReg.ABSTRACTS].r.fields.values()
    abstracts_w = cpu.debug.dmi_regs[DMIReg.ABSTRACTS].w.fields.values()

    vcd_traces = [
        # jtag_loc.tdi,
        # jtag_loc.tdo,
        # jtag_loc.port.tdo,
        # jtag_loc.tck,
        # jtag_loc.tms,
        # jtag_loc.rising_tck,
        # jtag_loc.falling_tck,
        # jtag_loc.port.tms,
        # jtag_loc.dr,
        # jtag_loc.dr.w,
        main_clk_sig,
        jtag_fsm_sig,
        jtag_loc.ir,
        cpu.debug.dmi_op,
        cpu.debug.dmi_address,
        cpu.debug.dmi_data,
        jtag_loc.regs[JtagIR.DMI].update,
        jtag_loc.regs[JtagIR.DMI].capture,
        jtag_loc.DATA_WRITE,
        jtag_loc.DATA_READ,
        cpu.debug.ONWRITE,
        cpu.debug.ONREAD,
        cpu.debug.HANDLER,
        cpu.debug.DBG_DMI_ADDR,

        # *dmcontrol_r,
        jtag_loc.BAR,
        *dmcontrol_w,
        jtag_loc.BAR,
        *dmcontrol_r,
        jtag_loc.BAR,
        jtag_loc.regs[JtagIR.DMI].r.op,
        jtag_loc.BAR,
        *hartinfo_w,
        jtag_loc.BAR,
        *abstracts_w,
    ]

    with sim.write_vcd("jtag.vcd", "jtag.gtkw", traces=vcd_traces):
        sim.run()


def test_jtag(_: JtagTestCase):
    assert_jtag_test(
        name="JTAG IDCODE+BYPASS test",
        timeout_cycles=1000,
    )


@parametrized
def mem_test(f, cases: List[MemTestCase]):
    @pytest.mark.parametrize("test_case", cases)
    @rename(f.__name__)
    def aux(test_case):
        assert_mem_test(test_case)
        f(test_case)

    return aux

@parametrized
def jtag_test(f, cases: List[JtagTestCase]):
    @pytest.mark.parametrize("test_case", cases)
    @rename(f.__name__)
    def aux(test_case):
        test_jtag(test_case)
        f(test_case)
    return aux