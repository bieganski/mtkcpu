from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from io import StringIO
from itertools import count
from typing import List, Optional

from nmigen.hdl.ast import Signal, Value
from nmigen.hdl.ir import Fragment
from nmigen import Elaboratable, Signal, ClockDomain
from nmigen.back.pysim import Simulator
import pytest

from mtkcpu.asm.asm_dump import dump_asm
from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.utils.common import START_ADDR
from mtkcpu.utils.decorators import parametrized, rename
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.sim_tests import (get_sim_memory_test,
                                          get_sim_register_test,
                                          get_sim_jtag_controller,
                                          get_sim_jtag_examine_passive)
from mtkcpu.units.debug.jtag import JtagIR
from mtkcpu.units.debug.top import DMIReg, DMICommand

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

@dataclass(frozen=True)
class JtagOCDTestCase:
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


# Returns dict with keys:
# "sim" - Simulator object
# "frag" - Fragment object
# "vcd_traces" - List of JTAG/DM signals to be traced
# "jtag_fsm" - JTAG FSM
def create_jtag_simulator(cpu):
    # cursed stuff for retrieving jtag FSM state for 'traces=vcd_traces' variable
    # https://freenode.irclog.whitequark.org/nmigen/2020-07-26#27592720;
    frag = Fragment.get(cpu, platform=None)
    jtag_fsm = frag.find_generated("debug", "jtag", "fsm")
    sim = Simulator(frag)
    sim.add_clock(1e-6)

    jtag_fsm_sig = jtag_fsm.state
    main_clk_sig = sim._fragment.domains["sync"].clk

    jtag_loc = cpu.debug.jtag

    dmcontrol_r = cpu.debug.dmi_regs[DMIReg.DMCONTROL].r.fields.values()
    dmcontrol_w = cpu.debug.dmi_regs[DMIReg.DMCONTROL].w.fields.values()

    hartinfo_r = cpu.debug.dmi_regs[DMIReg.HARTINFO].r.fields.values()
    hartinfo_w = cpu.debug.dmi_regs[DMIReg.HARTINFO].w.fields.values()

    abstracts_r = cpu.debug.dmi_regs[DMIReg.ABSTRACTS].r.fields.values()
    abstracts_w = cpu.debug.dmi_regs[DMIReg.ABSTRACTS].w.fields.values()

    dmstatus_r = cpu.debug.dmi_regs[DMIReg.DMSTATUS].r.fields.values()
    dmstatus_w = cpu.debug.dmi_regs[DMIReg.DMSTATUS].w.fields.values()

    command_w = cpu.debug.dmi_regs[DMIReg.COMMAND].w.fields.values()
    command_r = cpu.debug.dmi_regs[DMIReg.COMMAND].r.fields.values()

    data0_w = cpu.debug.dmi_regs[DMIReg.DATA0].w.fields.values()
    data0_r = cpu.debug.dmi_regs[DMIReg.DATA0].r.fields.values()

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
        jtag_loc.DMI_WRITE,
        cpu.debug.ONWRITE,
        cpu.debug.ONREAD,
        cpu.debug.HANDLER,
        cpu.debug.DBG_DMI_ADDR,

        jtag_loc.BAR,
        *data0_r,

        # *dmcontrol_r,
        # jtag_loc.BAR,
        # *dmcontrol_w,
        # jtag_loc.BAR,
        # *dmcontrol_r,
        # jtag_loc.BAR,
        # jtag_loc.regs[JtagIR.DMI].r.op,
        # jtag_loc.BAR,
        # *dmstatus_r,
        # *hartinfo_w,
        jtag_loc.BAR,
        *abstracts_w,
        jtag_loc.BAR,
        *abstracts_r,
        jtag_loc.BAR,
        *command_w,
        jtag_loc.BAR,
        *cpu.debug.command_regs[DMICommand.AccessRegister].fields.values(),
        jtag_loc.BAR,
        *dmstatus_r,
        jtag_loc.BAR,
        *dmcontrol_w,

        cpu.gprf_debug_r_data,
        cpu.gprf_debug_r_addr,
        cpu.halt,
    ]
    return {
        "sim": sim,
        "frag": frag,
        "vcd_traces": vcd_traces,
        "jtag_fsm": jtag_fsm,
    }


def assert_jtag_ocd_examine_test(
    name: str
):
    from subprocess import Popen, PIPE
    from pathlib import Path

    # same as './src/REMOTE_BITBANG.cfg' below"
    OCD_CFG = """
interface remote_bitbang
remote_bitbang_host localhost
remote_bitbang_port 9824

set _CHIPNAME riscv
jtag newtap $_CHIPNAME cpu -irlen 5 -expected-id 0x10e31913

set _TARGETNAME $_CHIPNAME.cpu
target create $_TARGETNAME riscv -chain-position $_TARGETNAME

gdb_report_data_abort enable

# init
# halt

    """
    OCD_PATH = Path("/home/mateusz/github/openocd_riscv")
    OCD_CMD = "sleep 1 && ./src/openocd -f ./src/REMOTE_BITBANG.cfg"
    OCD_OUTPUT_REDIRECT_PATH = OCD_PATH / Path("OUT")

    import sys
    output = open(OCD_OUTPUT_REDIRECT_PATH, "w") # sys.stdout

    print(f"=== OCD Output redirected to {OCD_OUTPUT_REDIRECT_PATH} file")

    cpu = MtkCpu(reg_init=[0x2137 + i for i in range(32)], with_debug=True)
    
    sim_gadgets = create_jtag_simulator(cpu)
    sim, vcd_traces, jtag_fsm = [sim_gadgets[k] for k in ["sim", "vcd_traces", "jtag_fsm"]]
    
    sim.add_sync_process(
        get_sim_jtag_controller(cpu=cpu, timeout_cycles=10000, jtag_fsm=jtag_fsm)
    )
    sim.add_sync_process(
        get_sim_jtag_examine_passive(cpu=cpu, jtag_fsm=jtag_fsm)
    )

    process = Popen(OCD_CMD, stdout=output, stderr=output, cwd=OCD_PATH, shell=True)

    # stdout, stderr = process.communicate()
    with sim.write_vcd("jtag.vcd", "jtag.gtkw", traces=vcd_traces):
        # import time
        # time.sleep(3.0)
        sim.run()
        
    stdout, stderr = process.communicate()
    


def assert_jtag_test(
    name: str,
    timeout_cycles: Optional[int],
):
    from nmigen.back.pysim import Simulator

    cpu = MtkCpu(reg_init=[0x1000 + i for i in range(32)], with_debug=True)
    
    sim_gadgets = create_jtag_simulator(cpu)
    sim, vcd_traces, jtag_fsm = [sim_gadgets[k] for k in ["sim", "vcd_traces", "jtag_fsm"]]
    
    sim.add_sync_process(
        get_sim_jtag_controller(cpu=cpu, timeout_cycles=timeout_cycles, jtag_fsm=jtag_fsm)
    )    

    with sim.write_vcd("jtag.vcd", "jtag.gtkw", traces=vcd_traces):
        sim.run()


def test_jtag(_: JtagTestCase):
    assert_jtag_test(
        name="JTAG manual test",
        timeout_cycles=1000,
    )

def test_jtag_ocd_examine(_: JtagOCDTestCase):
    assert_jtag_ocd_examine_test(
        name="JTAG openOCD examine test",
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

@parametrized
def jtag_ocd_examine_test(f, cases: List[JtagOCDTestCase]):
    @pytest.mark.parametrize("test_case", cases)
    @rename(f.__name__)
    def aux(test_case):
        test_jtag_ocd_examine(test_case)
        f(test_case)

    return aux