from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from itertools import count
from typing import List, Optional

from nmigen.hdl.ir import Elaboratable, Fragment
from nmigen.sim import Simulator
from nmigen.sim.core import Passive
import pytest
from typing import OrderedDict

from mtkcpu.asm.asm_dump import dump_asm
from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.utils.common import CODE_START_ADDR, MEM_START_ADDR, EBRMemConfig
from mtkcpu.utils.decorators import parametrized, rename
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.sim_tests import (get_sim_memory_test,
                                          get_sim_register_test,
                                          get_sim_jtag_controller,
                                          get_ocd_checkpoint_checker)
from mtkcpu.units.debug.top import DMIReg, DMICommand
from mtkcpu.units.loadstore import MemoryArbiter

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
    with_ocd : bool
    with_checkpoints : bool

@dataclass(frozen=True)
class ComponentTestbenchCase:
    name: str
    component_type : Elaboratable

def capture_write_transactions(cpu : MtkCpu, dict_reference : OrderedDict) -> OrderedDict:
    def f():
        yield Passive()
        content = dict_reference
        wp = cpu.arbiter.ebr.wp
        mem = cpu.arbiter.ebr.mem._array
        while(True):
            en = yield wp.en
            addr = yield wp.addr
            if en:
                yield
                data = yield mem[addr]
                content[addr << 2] = data
            yield
    return f

def reg_test(
    name: str,
    timeout_cycles: Optional[int],
    reg_num: int,
    expected_val: Optional[int],
    expected_mem: Optional[MemoryContents],
    reg_init: RegistryContents,
    mem_cfg: EBRMemConfig,
    verbose: bool = False,
):

    cpu = MtkCpu(
        reg_init=reg_init.reg, 
        with_debug=False, # XXX
        mem_config=mem_cfg
    )

    sim = Simulator(cpu)
    sim.add_clock(1e-6)

    assert (reg_num is None and expected_val is None) or (
        reg_num is not None and expected_val is not None
    )
            
    # Since nMigen's 'Memory' instance simulation in included,
    # we don't need to use custom implementation (however some coverage drop
    # is present - 'Memory' class is assumed single-cycle-access, while
    # 'get_sim_memory_test' processing delay is random).
    # sim.add_sync_process(get_sim_memory_test(cpu=cpu, mem_dict=mem_dict))
    # instead only collect write transactions directly on a bus.
    result_mem = {}
    sim.add_sync_process(capture_write_transactions(cpu=cpu, dict_reference=result_mem))
    
    sim.add_sync_process(
        get_sim_register_test(
            name=name,
            cpu=cpu,
            reg_num=reg_num,
            expected_val=expected_val,
            timeout_cycles=timeout_cycles,
        )
    )

    # from nmigen.back import verilog
    # s = verilog.convert(cpu)
    # open("cpu.v", "w").write(s)

    with sim.write_vcd("cpu.vcd"):
        sim.run()

    if expected_mem is not None:
        MemoryContents(result_mem).assert_equality(expected_mem)


def get_code_mem(case: MemTestCase) -> MemoryContents:
    if case.source_type == MemTestSourceType.TEXT:
        code = dump_asm(case.source, verbose=False)
        return MemoryContents(
            memory=dict(zip(count(CODE_START_ADDR, 4), code)),
        )
    else:
        from mtkcpu.utils.common import read_elf, compile_source
        tmp_elf_path = "tmp.elf"
        compile_source(case.source, tmp_elf_path)
        return MemoryContents(
            memory=read_elf(tmp_elf_path, verbose=False)
        )



def memory_arbiter_tb():
    mem = {
        0x1000: 0xdead,
        0x1004: 0xbeef,
    }
    assert len(mem) >= 2
    a1, a2 = min(mem.keys()), max(mem.keys())
    start_addr = min(mem.keys())
    
    mem_cfg = EBRMemConfig(
        mem_addr=start_addr,
        mem_size_words=10,
        mem_content_words = [v for k, v in sorted(mem.items())],
        simulate=True,
    )
    m = MemoryArbiter(mem_cfg)
    p1 = m.port(priority=1)
    p2 = m.port(priority=2)

    def f():
        # both will request transaction simultaneously, lower priority wins
        yield p1.en.eq(1)
        yield p2.en.eq(1)

        yield p1.store.eq(0)
        yield p2.store.eq(0)

        yield p1.addr.eq(a1)
        yield p2.addr.eq(a2)
        yield

        for _ in range(10):
            ack = yield m.generic_bus.ack
            data = yield m.generic_bus.read_data
            if ack:
                assert data == mem[a1]
                yield p1.en.eq(0)
                break
            yield
        
        yield
        
        # first one finished, second starts.
        for _ in range(10):
            ack = yield m.generic_bus.ack
            data = yield m.generic_bus.read_data
            if ack:
                assert data == mem[a2], data
                yield p2.en.eq(0)
                break
            yield
            
    return m, f


def unit_testbench(case: ComponentTestbenchCase):
    if case.component_type == MemoryArbiter:
        m, f = memory_arbiter_tb()
    else:
        print(f"===== Skipping not covered type {case.component_type}")
        return

    sim = Simulator(m)
    sim.add_clock(1e-6)
    sim.add_sync_process(f)

    with sim.write_vcd(f"{case.name}.vcd"):
        sim.run()
    

def assert_mem_test(case: MemTestCase):
    name = case.name
    reg_init = case.reg_init or RegistryContents.empty()
    mem_init = case.mem_init or MemoryContents.empty()

    program = get_code_mem(case)
    if case.mem_init:
        case.mem_init.shift_addresses(MEM_START_ADDR)
    program.patch(mem_init, can_overlap=False)
    if program.size == 0:
        raise ValueError("Memory content cannot be empty! At least single instruction must be present.")

    mem_cfg = EBRMemConfig.from_mem_dict(
        start_addr=MEM_START_ADDR,
        num_bytes=256, # for sim support 2-byte addressing
        simulate=True,
        mem_dict=program
    )

    reg_test(
        name=name,
        timeout_cycles=case.timeout,
        reg_num=case.out_reg,
        expected_val=case.out_val,
        expected_mem=case.mem_out,
        reg_init=reg_init,
        mem_cfg=mem_cfg,
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
        cpu.EBREAK,
        cpu.FENCE,
        cpu.debug.dmi_op,
        cpu.debug.dmi_address,
        cpu.debug.dmi_data,
        # jtag_loc.regs[JtagIR.DMI].update,
        # jtag_loc.regs[JtagIR.DMI].capture,
        # jtag_loc.DATA_WRITE,
        # jtag_loc.DATA_READ,
        # jtag_loc.DMI_WRITE,
        cpu.DEBUG_CTR,
        cpu.debug.ONWRITE,
        cpu.debug.ONREAD,
        # cpu.debug.HANDLER,
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

        cpu.gprf_debug_data,
        cpu.gprf_debug_addr,
        cpu.halt,
    ]
    return {
        "sim": sim,
        "frag": frag,
        "vcd_traces": vcd_traces,
        "jtag_fsm": jtag_fsm,
    }




# Make sure that 'OCD_CWD' points to directory with VexRiscv's fork of openOCD:
# https://github.com/SpinalHDL/openocd_riscv
# Compile it according to instructions in README in repository above.
def run_openocd(delay=1):
    from pathlib import Path

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
    OCD_CWD = Path("/home/mateusz/github/openocd_riscv")
    OCD_CMD = "sleep %s && ./src/openocd -f %s"
    OCD_OUTPUT_REDIRECT_PATH = OCD_CWD / "OUT.txt"

    output = OCD_OUTPUT_REDIRECT_PATH.open(mode='w')

    print(f"=== OCD Output redirected to {OCD_OUTPUT_REDIRECT_PATH} file")

    from subprocess import Popen, DEVNULL
    from tempfile import NamedTemporaryFile
    with NamedTemporaryFile(mode='w', delete=False) as f:
        ocd_cfg_fname = f.name
        f.write(OCD_CFG)
    OCD_CMD = OCD_CMD % (delay, ocd_cfg_fname)
    if not OCD_CWD.exists() or not OCD_CWD.is_dir():
        raise ValueError(f"Please make sure that path: {OCD_CWD} is existing directory with src/openocd executable!")
    process = Popen(OCD_CMD, cwd=OCD_CWD, shell=True, stderr=DEVNULL, stdout=output)


# def assert_jtag_test(
#     name: str,
#     timeout_cycles: Optional[int],
#     with_ocd=False,
#     with_checkpoints=False,
# ):

    if with_ocd:
        run_openocd(delay=1)
    
    cpu = MtkCpu(reg_init=[0x1000 + i for i in range(32)], with_debug=True)    
    sim_gadgets = create_jtag_simulator(cpu)
    sim, vcd_traces, jtag_fsm = [sim_gadgets[k] for k in ["sim", "vcd_traces", "jtag_fsm"]]

    processes = [
        get_sim_memory_test(cpu=cpu, mem_dict=MemoryContents.empty()),
        get_sim_jtag_controller(cpu=cpu, timeout_cycles=timeout_cycles, jtag_fsm=jtag_fsm),
    ]

    if with_checkpoints:
        processes.append(get_ocd_checkpoint_checker(cpu))

    for p in processes:
        sim.add_sync_process(p)

    with sim.write_vcd("jtag.vcd", "jtag.gtkw", traces=vcd_traces):
        sim.run()


# def test_jtag(test_case: JtagTestCase):
#     assert_jtag_test(
#         name="JTAG test (with openocd and gdb)",
#         timeout_cycles=1000, # TODO timeout not used
#         with_ocd=test_case.with_ocd,
#         with_checkpoints=test_case.with_checkpoints
#     )

@parametrized
def component_testbench(f, cases: List[ComponentTestbenchCase]):
    @pytest.mark.parametrize("test_case", cases)
    @rename(f.__name__)
    def aux(test_case):
        unit_testbench(test_case)
        f(test_case)
    return aux


@parametrized
def mem_test(f, cases: List[MemTestCase]):
    @pytest.mark.parametrize("test_case", cases)
    @rename(f.__name__)
    def aux(test_case):
        assert_mem_test(test_case)
        f(test_case)
    return aux

# @parametrized
# def jtag_test(f, cases: List[JtagTestCase]):
#     @pytest.mark.parametrize("test_case", cases)
#     @rename(f.__name__)
#     def aux(test_case):
#         test_jtag(test_case)
#         f(test_case)

#     return aux
