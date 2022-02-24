from dataclasses import dataclass
from pathlib import Path

from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.utils.common import EBRMemConfig, read_elf
from mtkcpu.utils.tests.memory import MemoryContents

from amaranth.sim import Simulator

from riscvmodel.code import decode, Instruction
from typing import Optional
import pytest

import sys
from instr_trace_compare import compare_trace_csv
import tempfile

def disassemble(instr : int) -> Optional[Instruction]:
    try:
        return decode(instr)
    except Exception as e:
        logging.info(f"ERROR during converting {instr} instruction to string!: {e}")
        return None
import logging

from riscv_trace_csv import RiscvInstructionTraceEntry, RiscvInstructionTraceCsv

"""
    google/riscv-dv code-generator for comparison uses specific csv format,
    to compare against e.g. Spike ground truth.
    It will be written by simulator function to 'csv_output' file. 
"""
def riscv_dv_sim_process(cpu : MtkCpu, iss_csv : Path, compare_every: int, csv_output: Path):
    def aux():
        csv_output_fd = csv_output.open("w")
        csv_writer = RiscvInstructionTraceCsv(csv_fd=csv_output_fd)
        csv_writer.start_new_trace()

        total_num_processed = -1
        prev_checkpoint = 0
        do_compare = lambda : total_num_processed - prev_checkpoint >= compare_every
        while True:
            instr : int = yield cpu.instr
            pc : int = yield cpu.pc

            if (yield cpu.fetch):
                total_num_processed += 1
                if do_compare():
                    csv_output_fd.flush()
                    logging.info(f"total: {total_num_processed}, previous checkpoint: {prev_checkpoint}. calling 'compare_trace_csv'...")
                    prev_checkpoint = total_num_processed
                    # order of passing mtkcpu and spike matters - we allow only first passed log to be shorter
                    compare_trace_csv(csv_output.absolute(), iss_csv.absolute(), "mtkcpu", "spike", log=0)
                
                instr_disas = disassemble(instr)
                logging.info(f"{hex(pc)}: {hex(instr)} : {instr_disas}")
                instr_str = str(instr_disas) if instr_disas else "unknown"
                
                entry = RiscvInstructionTraceEntry()
                entry.pc = hex(pc)[2:]
                entry.instr_str = instr_str
                instr_str_splitted = " ".join(instr_str.split()).split(" ")
                reg_name = instr_str_splitted[1][:-1] if len(instr_str_splitted) > 1 else "NO REG NAME"
                entry.binary = hex(instr)[2:]
                entry.mode = "3"  # '3' stands for machine mode
                # entry.gpr value is unknown, need to calculate it

                if instr == 0x73: # 'ecall' - Spike simulation finishes with ecall. By default we compare with Spike.
                    logging.critical(f"found {hex(instr)} : {instr_str} intruction: finishing simulation")
                    return
                
                timeout_cyc = 50
                found = False
                
                for _ in range(timeout_cyc):
                    if (yield cpu.writeback):
                        if not (yield cpu.should_write_rd):
                            logging.info(f"detected instruction that doesn't write to rd. - {instr_str}")
                            found = True
                            csv_output_fd.write(f"# {hex(instr)}: {instr_str}\n")
                            break
                        en = yield cpu.reg_write_port.en
                        assert en
                        rd = yield cpu.reg_write_port.addr
                        data = yield cpu.reg_write_port.data
                        if instr_disas and getattr(instr_disas, "rd", None):
                            if rd != instr_disas.rd:
                                raise ValueError(f"{hex(instr)} reg {rd} != expected {instr_disas.rd}")
                            else:
                                found = True
                                entry.gpr = [ f"{reg_name}:{hex(data)[2:]}" ]
                                
                                # depending on '-f' param passed to 'scripts/spike_log_to_trace_csv.py' inside riscv-dv repo,
                                # we need either to print register-state-changing instructions only (like here),
                                # or all instructions, then we would put the line below after the loop. 
                                csv_writer.write_trace_entry(entry)
                                break
                    yield
                if not found:
                    raise ValueError("No register write observed!")
            yield
    return aux

@dataclass(frozen=False)
class RiscvDvTestConfig:
    test_name : str
    compare_every: int

    def __post_init__(self):
        self.start_addr = 0x8000_0000 # same as in riscv-dv/scripts/link.ld
        self.asserts_dir = Path(__file__).absolute().parent / "riscv_dv_assets"
        self.test_elf = self.asserts_dir / f"{self.test_name}_0.o"
        self.iss_csv = self.asserts_dir / f"{self.test_name}.csv"

        for f in [self.asserts_dir, self.test_elf, self.iss_csv]:
            if not f.exists():
                raise ValueError(f"{f} does not exists! Needed for {self.test_name} riscv-dv test case.")


@pytest.mark.skip
@pytest.mark.parametrize("cfg", 
    [
        RiscvDvTestConfig("riscv_u_mode_rand_test", 1000), 
        RiscvDvTestConfig("riscv_arithmetic_basic_test", 1000), 
    ]
)
def test_riscv_dv(cfg: RiscvDvTestConfig):
    sys.setrecursionlimit(10**6) # otherwise amaranth/sim/_pyrtl.py:441: RecursionError, because of huge memory size
    max_code_size = cfg.test_elf.stat().st_size
    program = read_elf(cfg.test_elf)
    mem_cfg = EBRMemConfig.from_mem_dict(
        start_addr=cfg.start_addr,
        num_bytes=max_code_size,
        simulate=True,
        mem_dict=MemoryContents(program),
    )

    cpu = MtkCpu(
        with_debug=False,
        mem_config=mem_cfg
    )

    sim = Simulator(cpu)
    sim.add_clock(1e-6)

    traces = [
        cpu.pc,
        cpu.instr,
        cpu.rd,
        cpu.should_write_rd,
        *cpu.csr_unit.satp.fields.values(),
        cpu.exception_unit.current_priv_mode,
        
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
        cpu.arbiter.error_code,
    ]

    csv_output = tempfile.NamedTemporaryFile(
        suffix=f".mtkcpu.{cfg.test_name}.csv", 
        dir=Path(__file__).parent.name, 
        delete=False
    )
    fn = riscv_dv_sim_process(
        cpu=cpu,
        iss_csv=cfg.iss_csv,
        compare_every=cfg.compare_every,
        csv_output=Path(csv_output.name),
    )
    sim.add_sync_process(fn)
    
    with sim.write_vcd("cpu.vcd", "cpu.gtkw", traces=traces):
        sim.run()
    print("== Waveform dumped to cpu.vcd file")
