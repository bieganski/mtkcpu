from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique
from itertools import count
from typing import Dict, List, Optional, OrderedDict
import pytest
from pathlib import Path
import subprocess
from tempfile import NamedTemporaryFile

from amaranth.hdl.ast import Signal, Const
from amaranth.hdl.ir import Elaboratable, Fragment
from amaranth.sim import Simulator
from amaranth.sim.core import Active, Passive
from amaranth.hdl import rec
from amaranth import Module, Cat, Signal

from mtkcpu.asm.asm_dump import dump_asm
from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.global_config import Config
from mtkcpu.units.csr import CsrUnit
from mtkcpu.units.exception import ExceptionUnit
from mtkcpu.utils.common import CODE_START_ADDR, MEM_START_ADDR, EBRMemConfig, read_elf
from mtkcpu.utils.decorators import parametrized, rename
from mtkcpu.utils.tests.memory import MemoryContents
from mtkcpu.utils.tests.registers import RegistryContents
from mtkcpu.utils.tests.sim_tests import (get_sim_memory_test,
                                          get_sim_register_test,
                                          get_sim_jtag_controller,
                                          get_ocd_checkpoint_checker)
from mtkcpu.units.debug.types import *
from mtkcpu.units.loadstore import MemoryArbiter, WishboneBusRecord
from mtkcpu.units.mmio.gpio import GPIO_Wishbone
from mtkcpu.utils.tests.dmi_utils import *
from mtkcpu.utils.misc import get_color_logging_object

logging = get_color_logging_object()

@unique
class MemTestSourceType(str, Enum):
    TEXT = "text"
    RAW = "raw"


@dataclass
class CpuTestbenchCase:
    name : str
    sw_project: str
    try_compile: bool

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
    mem_size_kb: int = 1
    shift_mem_content: bool = True # 0x1000 becomes 0x8000_1000 if mem. start address is 0x8000_0000

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
            
    # Since Amaranth HDL's 'Memory' instance simulation in included,
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

    csr_unit : CsrUnit = cpu.csr_unit
    # frag = Fragment.get(cpu, platform=None)
    # main_fsm = frag.find_generated("fsm")
    e = cpu.exception_unit
    sim_traces = [
        # main_fsm.state,
        # e.m_instruction,
        # e.mtval.value,
        # csr_unit.mtvec.base,
        # csr_unit.mtvec.mode,
        # *csr_unit.mepc.fields.values(),
        *csr_unit.mcause.fields.values(),
        *csr_unit.satp.fields.values(),
        # *csr_unit.mie.fields.values(),
        # *csr_unit.mstatus.fields.values(),
        # *csr_unit.mtime.fields.values(),
        # *csr_unit.mtimecmp.fields.values(),
        cpu.instr,
        cpu.pc,
        # csr_unit.rs1,
        # csr_unit.csr_idx,
        # csr_unit.rd,
        # csr_unit.rd_val,
        # csr_unit.vld,
        # csr_unit.ONREAD,
        # csr_unit.ONWRITE,
        cpu.arbiter.pe.i,
        cpu.arbiter.pe.o,
        cpu.arbiter.pe.none,
        cpu.arbiter.bus_free_to_latch,

        cpu.arbiter.error_code,
        cpu.arbiter.addr_translation_en,
        cpu.arbiter.translation_ack,
        cpu.arbiter.start_translation,
        cpu.arbiter.phys_addr,
        cpu.arbiter.root_ppn,

        *cpu.arbiter.pte.fields.values(),

        cpu.arbiter.generic_bus.addr,
        cpu.arbiter.generic_bus.read_data,
        cpu.arbiter.vpn,
    ]

    # from amaranth.back import verilog
    # s = verilog.convert(cpu)
    # open("cpu.v", "w").write(s)

    with sim.write_vcd("cpu.vcd", "cpu.gtkw", traces=sim_traces):
        sim.run()

    if expected_mem is not None:
        MemoryContents(result_mem).assert_equality(expected_mem)


def get_code_mem(case: MemTestCase, mem_size_kb: int) -> MemoryContents:
    if case.source_type == MemTestSourceType.TEXT:
        code = dump_asm(case.source, verbose=False)
        return MemoryContents(
            memory=dict(zip(count(CODE_START_ADDR, 4), code)),
        )
    elif case.source_type == MemTestSourceType.RAW:
        from mtkcpu.utils.common import read_elf, compile_source
        import tempfile
        with tempfile.NamedTemporaryFile(
            suffix=".elf",
            dir=Path(__file__).parent
        ) as tmp_elf:
            source = f"""
            .global start
            {case.source}
            """
            compile_source(source, tmp_elf.name, mem_size_kb=mem_size_kb)
            elf_content = read_elf(tmp_elf.name, verbose=False)
        return MemoryContents(
            memory=elf_content
        )
    else:
        assert False

def gpio_tb():
    led1, led2 = Signal(), Signal()
    bus  = WishboneBusRecord()
    signal_map = [0 for _ in range(32)]
    idx1, idx2 = 0, 20
    signal_map[idx1] = led1
    signal_map[idx2] = led2
    signal_map_gen = lambda platform: signal_map

    m = GPIO_Wishbone(signal_map_gen)
    m.init_bus_slave(bus)
    def f():
        def wait(timeout=10):
            for _ in range(timeout):
                yield
        def wait_ack(timeout=10):
            lst = []
            for _ in range(timeout):
                ack = yield bus.ack
                lst.append(ack)
                yield
            assert 1 in lst

        yield from wait()

        l1, l2 = (yield led1), (yield led2)
        assert not l1
        assert not l2
        
        yield bus.cyc.eq(1)
        yield bus.sel.eq(0b0001)
        yield bus.we.eq(1)
        yield bus.adr.eq(0)
        yield bus.dat_w.eq(0xffff_ffff)
        yield from wait_ack()

        l1, l2 = (yield led1), (yield led2)
        assert l1
        assert not l2

        yield bus.cyc.eq(0)
        wait()
        yield bus.cyc.eq(1)
        yield bus.sel.eq(0b1111)

        yield from wait_ack()

        l1, l2 = (yield led1), (yield led2)
        assert l1
        assert l2
        
    return m, f

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
    csr_unit = CsrUnit(in_machine_mode=Signal(reset=1), in_debug_mode=Const(0))
    m = MemoryArbiter(mem_config=mem_cfg, with_addr_translation=False, csr_unit=csr_unit, exception_unit=ExceptionUnit(Signal(2, reset=0b11), csr_unit))
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
    elif case.component_type == GPIO_Wishbone:
        m, f = gpio_tb()
    else:
        print(f"===== Skipping not covered type {case.component_type}")
        return

    sim = Simulator(m)
    sim.add_clock(1e-6)
    sim.add_sync_process(f)

    with sim.write_vcd(f"{case.name}.vcd"):
        sim.run()


# returns ELF path
def compile_sw_project(proj_name : str) -> Path:
    sw_dir = Path(__file__).parent.parent.parent / "sw"
    proj_dir = sw_dir / proj_name
    if not proj_dir.exists() or not proj_dir.is_dir():
        raise ValueError(f"Compilation failed: Directory {proj_dir} does not exists!")
    from mtkcpu.utils.linker import write_linker_script
    write_linker_script(sw_dir / "common" / "linker.ld", CODE_START_ADDR)
    process = subprocess.Popen(f"make -B", cwd=proj_dir, shell=True)
    process.communicate()
    if process.returncode:
        raise ValueError(f"Compilation failed! {proj_name} (inside {proj_dir})")
    elf_path = proj_dir / "build" / f"{proj_name}.elf"
    if not elf_path.exists():
        raise ValueError(f"Error: Compilation returned 0 (ok), but elf {elf_path} doesnt exists!")
    return elf_path

def virtual_mem_translation_test():
    pass

def cpu_testbench_test(case : CpuTestbenchCase):
    root_dir = Path(__file__).parent.parent.parent
    if case.try_compile:
        proj_name = case.sw_project
        compile_sw_project(proj_name)
        print("Ok, compile successed!")
        elf_path = root_dir / f"sw/{case.sw_project}/{case.sw_project}.elf"
    else:
        elf_path = root_dir / f"tests/tb_assets/{case.sw_project}.elf"
    
    assert elf_path.exists()
    program = read_elf(elf_path)
    
    mem_cfg = EBRMemConfig.from_mem_dict(
        start_addr=MEM_START_ADDR,
        num_bytes=1024,
        simulate=True,
        mem_dict=MemoryContents(program),
    )

    cpu = MtkCpu(
        with_debug=False,
        mem_config=mem_cfg
    )

    sim = Simulator(cpu)
    sim.add_clock(1e-6)

    def get_last_instr_addr(elfpath : Path):
        from elftools.elf.elffile import ELFFile
        elf = ELFFile(elfpath.open("rb"))
        symtab = elf.get_section_by_name('.symtab')
        assert symtab
        from mtkcpu.global_config import Config
        try:
            sym = Config.after_main_sym_name
            last_instr = symtab.get_symbol_by_name(sym)[0]
        except IndexError:
            raise ValueError(f"ERROR: {elfpath} ELF does not have {sym} symbol! Check your start.S file.")
        e = last_instr.entry
        addr = e.st_value
        return addr

    def gpio_fn(timeout=200_000):
        yield
        prev_led = None
        for _ in range(timeout):
            led = yield cpu.arbiter.gpio.signal_map[1]
            if led != prev_led:
                print(f"Led changed state, finishing simulation!")
                return
            yield

    def uart_tx_fn(timeout=50_000):
        yield
        prev_tx = None
        txs = []
        for _ in range(timeout):
            pass
            tx = yield cpu.arbiter.uart.serial.tx
            if tx != prev_tx:
                # tx data line edge
                txs.append(tx)
                prev_tx = tx
            if len(txs) > 10:
                print("OK, UART tx data line is working! sim passed")
                return
            yield

    elf_path_str = str(elf_path).lower()
    if "blink" in elf_path_str:
        f = gpio_fn
    elif "uart_tx" in elf_path_str:
        f = uart_tx_fn
    else:
        assert False, elf_path_str

    sim.add_sync_process(f)
    
    with sim.write_vcd("cpu.vcd"):
        sim.run()
    print("== Waveform dumped to cpu.vcd file")


def assert_mem_test(case: MemTestCase):
    name = case.name
    reg_init = case.reg_init or RegistryContents.empty()
    mem_init = case.mem_init or MemoryContents.empty()
    
    if case.mem_size_kb > 1:
        # otherwise, it raises RecursionError
        import sys
        sys.setrecursionlimit(10**6)

    program = get_code_mem(case, mem_size_kb=case.mem_size_kb)
    if case.mem_init and case.shift_mem_content:
        case.mem_init.shift_addresses(MEM_START_ADDR)
    program.patch(mem_init, can_overlap=False)
    if program.size == 0:
        raise ValueError("Memory content cannot be empty! At least single instruction must be present.")

    mem_cfg = EBRMemConfig.from_mem_dict(
        start_addr=MEM_START_ADDR,
        num_bytes=1024 * case.mem_size_kb,
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
def create_jtag_simulator(monitor: DMI_Monitor, cpu: MtkCpu):
    # cursed stuff for retrieving jtag FSM state for 'traces=vcd_traces' variable
    # https://freenode.irclog.whitequark.org/amaranth/2020-07-26#27592720;
    frag = Fragment.get(monitor, platform=None)
    # jtag_fsm = frag.find_generated("debug", "jtag", "fsm")
    # sim = Simulator(frag) # XXX
    sim = Simulator(monitor)
    sim.add_clock(1e-6)

    # jtag_fsm_sig = jtag_fsm.state
    main_clk_sig = sim._fragment.domains["sync"].clk

    jtag_loc = cpu.debug.jtag

    dmi_regs = cpu.debug.dmi_regs

    # dmcontrol_r = dmi_regs[DMIReg.DMCONTROL].r.fields.values()
    # dmcontrol_w = dmi_regs[DMIReg.DMCONTROL].w.fields.values()

    # hartinfo_r = dmi_regs[DMIReg.HARTINFO].r.fields.values()
    # hartinfo_w = dmi_regs[DMIReg.HARTINFO].w.fields.values()

    # abstracts_r = dmi_regs[DMIReg.ABSTRACTCS].r.fields.values()
    # abstracts_w = dmi_regs[DMIReg.ABSTRACTCS].w.fields.values()

    # dmstatus_r = dmi_regs[DMIReg.DMSTATUS].r.fields.values()
    # dmstatus_w = dmi_regs[DMIReg.DMSTATUS].w.fields.values()

    # command_w = dmi_regs[DMIReg.COMMAND].w.fields.values()
    # command_r = dmi_regs[DMIReg.COMMAND].r.fields.values()

    # data0_w = dmi_regs[DMIReg.DATA0].w.fields.values()
    # data0_r = dmi_regs[DMIReg.DATA0].r.fields.values()

    vcd_traces = [
        # *monitor.cur_COMMAND_r.fields.values(),
        jtag_loc.tck_ctr,
        # jtag_loc.regs[JtagIR.DMI].update,
        # jtag_loc.regs[JtagIR.DMI].capture,
        # jtag_loc.DATA_WRITE,
        # jtag_loc.DATA_READ,
        # jtag_loc.DMI_WRITE,
        cpu.mtime,
        # cpu.debug.HANDLER,

        jtag_loc.BAR,
        # *data0_r,
        # *data0_w,
        jtag_loc.BAR,

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
        # *abstracts_w,
        jtag_loc.BAR,
        # *abstracts_r,
        jtag_loc.BAR,
        # *command_w,
        jtag_loc.BAR,
        # *cpu.debug.command_regs[DMICommand.AccessRegister].fields.values(),
        jtag_loc.BAR,
        # *dmstatus_r,
        jtag_loc.BAR,
        # *dmcontrol_w,

        cpu.gprf_debug_data,
        cpu.gprf_debug_addr,
    ]
    return {
        "sim": sim,
        "vcd_traces": vcd_traces,
        # "jtag_fsm": jtag_fsm,
    }


def run_gdb(
    gdb_executable: Path,
    elf_file: Path,
    stdout: Optional[Path] = None,
    stderr: Optional[Path] = None,
):

    gdb_cmd = f"""
set verbose on
set arch riscv:rv32
target extended-remote localhost:3333
set mem inaccessible-by-default off
set remotetimeout 10
file {elf_file.absolute()}
load
run    
"""

    stdout = stdout.open("w") if stdout else stdout
    stderr = stderr.open("w") if stderr else stderr

    with NamedTemporaryFile(dir=".", delete=False) as f:
        f.write(gdb_cmd.encode("ascii"))
        f.flush()

    process = subprocess.Popen(f"{gdb_executable} -x {f.name}", shell=True, stdout=stdout, stderr=stderr)


# Make sure that 'OCD_CWD' points to directory with VexRiscv's fork of openOCD:
# https://github.com/SpinalHDL/openocd_riscv
# Compile it according to instructions in README in repository above.
from typing import Generator

def run_openocd(
    openocd_executable: Path, 
    delay_execution_num_seconds: int,
    ) -> Generator[str, None, None]:
    """
    Runs subprocess with 'openocd_executable' invocation, after delay of 
    'delay_execution_num_seconds' seconds.
    
    TODO The openocd config used is hardcoded.
    """

    if not openocd_executable.exists():
        raise ValueError(f"Please make sure that path: {openocd_executable} is existing executable!")
    

    ocd_commands = """
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

    with NamedTemporaryFile(mode='w', delete=False) as f:
        ocd_cfg_fname = f.name
        f.write(ocd_commands)

    ocd_invocation = f"sleep {delay_execution_num_seconds} && {openocd_executable} -f {ocd_cfg_fname}"

    popen = subprocess.Popen(ocd_invocation, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True)

    for line in iter(popen.stderr.readline, ""):
        yield line

def get_git_root() -> Path:
    """
    WARNING: not to be used inside package!
    """
    import subprocess
    process = subprocess.Popen("git rev-parse --show-toplevel", shell=True, stdout=subprocess.PIPE)
    stdout, _ = process.communicate()
    return Path(stdout.decode("ascii").strip())


def build_software(sw_project_path: Path, cpu: MtkCpu) -> Path:
    "returns .elf path, previously asserting that it exists."
    from mtkcpu.utils.linker import write_linker_script
    from tempfile import NamedTemporaryFile

    linker_script = Path(NamedTemporaryFile(delete=False, suffix=".ld").name).absolute()

    write_linker_script(
        out_path=linker_script,
        mem_addr=cpu.mem_config.mem_addr,
        mem_size_kb=cpu.mem_config.arena_kb_ceiled,
    )

    process = subprocess.Popen(f"make -B LINKER_SCRIPT={linker_script}", cwd=sw_project_path, shell=True)
    process.communicate()
    
    elf_path = sw_project_path / "build" / f"{sw_project_path.name}.elf"
    assert elf_path.exists()
    
    return elf_path




def assert_jtag_test(
    timeout_cycles: Optional[int],
    openocd_executable: Path,
    gdb_executable: Path,
    with_checkpoints=False,
):
    cpu = MtkCpu(
        reg_init=[0xabcd + i for i in range(32)],
        mem_config=EBRMemConfig(mem_size_words=1000, mem_addr=0x8000, mem_content_words=None, simulate=False),
        with_debug=True,
    )

    sw_project_path = get_git_root() / "sw" / "just_loop"
    
    elf_path = build_software(sw_project_path=sw_project_path, cpu=cpu)

    lines = run_openocd(
        delay_execution_num_seconds=1,
        openocd_executable=openocd_executable
    )

    def run_gdb_when_ocd_ready():
        for line in lines:
            # from openocd/src/target/riscv/riscv-013.c:
            #
            #  /* Some regression suites rely on seeing 'Examined RISC-V core' to know
            # * when they can connect with gdb/telnet.
            # * We will need to update those suites if we want to change that text. */
            # logging.warn(line)
            if "Examined RISC-V core" in line:
                logging.info("Detected that openOCD successfully finished CPU examination! Running GDB..")
                run_gdb(
                    gdb_executable=gdb_executable,
                    elf_file=elf_path,
                    stdout=Path("GDB_STDOUT"),
                    stderr=Path("GDB_STDERR"),
                )
    
    from multiprocessing import Process
    gdb_process = Process(target=run_gdb_when_ocd_ready)
    gdb_process.start()
    # XXX gdb_process.join()

    dmi_monitor = DMI_Monitor(cpu=cpu)

    sim_gadgets = create_jtag_simulator(dmi_monitor, cpu)
    sim, vcd_traces = [sim_gadgets[k] for k in ["sim", "vcd_traces"]]

    processes = [
        monitor_cmderr(dmi_monitor),
        monitor_cpu_dm_if_error(dmi_monitor),
        monitor_cpu_and_dm_state(dmi_monitor),
        # monitor_pc_and_main_fsm(dmi_monitor),
        print_dmi_transactions(dmi_monitor),
        monitor_writes_to_gpr(dmi_monitor, gpr_num=8),
        monitor_halt_or_resume_req_get_ack(dmi_monitor),
        get_sim_memory_test(cpu=cpu, mem_dict=MemoryContents.empty()),
        get_sim_jtag_controller(cpu=cpu, timeout_cycles=timeout_cycles),
        monitor_writes_to_dcsr(dmi_monitor=dmi_monitor),
    ]

    with_checkpoints = False # XXX

    if with_checkpoints:
        processes.append(get_ocd_checkpoint_checker(cpu))

    for p in processes:
        sim.add_sync_process(p)

    with sim.write_vcd("jtag.vcd", "jtag.gtkw", traces=vcd_traces):
        sim.run()

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

@parametrized
def cpu_testbench(f, cases: List[CpuTestbenchCase]):
    @pytest.mark.parametrize("test_case", cases)
    @rename(f.__name__)
    def aux(test_case):
        cpu_testbench_test(test_case)
        f(test_case)
    return aux
