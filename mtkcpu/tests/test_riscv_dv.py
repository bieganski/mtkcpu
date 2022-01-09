from pathlib import Path
from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.utils.common import EBRMemConfig, read_elf
from mtkcpu.utils.tests.memory import MemoryContents

from amaranth.sim import Simulator

from riscvmodel.code import decode, Instruction
from typing import Optional

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
def riscv_dv_sim_process(cpu : MtkCpu, csv_output : Path = Path("test.csv")):
    def aux():
        csv_writer = RiscvInstructionTraceCsv(csv_fd=csv_output.open("w"))
        csv_writer.start_new_trace()
        prev_instr = 0x0

        for _ in range(20): # warm up
            instr = yield cpu.instr
            if instr == 0x0:
                yield
            else:
                break
        while True:
            instr : int = yield cpu.instr
            pc : int = yield cpu.pc

            if instr != prev_instr:
                # new instruction - everything 
                instr_disas = disassemble(instr)
                logging.info(f"{hex(instr)} : {instr_disas}")
                instr_str = str(instr_disas) if instr_disas else "unknown"
                entry = RiscvInstructionTraceEntry()
                entry.pc = hex(pc)[2:]
                entry.instr_str = instr_str
                instr_str_splitted = " ".join(instr_str.split()).split(" ")
                reg_name = instr_str_splitted[1][:-1] if len(instr_str_splitted) > 1 else "NO REG NAME"
                entry.binary = hex(instr)[2:]
                entry.mode = "3"  # 3 = machine mode
                # entry.gpr value is unknown, need to calculate it

                if instr == 0 or instr == 0x73:
                    # wrong instr (TODO trap) or 'ecall' 
                    logging.critical(f"found {hex(instr)} : {instr_str} intruction: finishing simulation")
                    return
                else:
                    # compute entry.csv
                    # TODO
                    # it will break on all instructions that do not perform register write,
                    # e.g. blt (without link)
                    timeout_cyc = 20
                    found = False
                    for _ in range(timeout_cyc):
                        en = yield cpu.reg_write_port.en
                        if en:
                            rd = yield cpu.reg_write_port.addr
                            data = yield cpu.reg_write_port.data
                            if instr_disas and getattr(instr_disas, "rd", None):
                                if rd != instr_disas.rd:
                                    raise ValueError(f"CPU logic error (instr {hex(instr)} : {instr_str}): destination register {rd} doesn't match expected {instr_disas.rd}")
                            found = True
                            entry.gpr = [ f"{reg_name}:{hex(data)[2:]}" ]
                            break
                        yield
                    if not found:
                        raise ValueError("No register write observed!")
                csv_writer.write_trace_entry(entry)
            prev_instr = instr
            yield
    return aux

RISCV_DV_START_ADDR = 0x8000_0000 # same as in riscv-dv/scripts/link.ld
RISCV_DV_TEST_ELF = Path("/home/mateusz/github/riscv-dv/out_2022-01-07/asm_test/riscv_arithmetic_basic_test_0.o")

def test_riscv_dv():
    import sys
    sys.setrecursionlimit(10**6) # otherwise amaranth/sim/_pyrtl.py:441: RecursionError
    max_code_size = RISCV_DV_TEST_ELF.stat().st_size
    program = read_elf(RISCV_DV_TEST_ELF)
    mem_cfg = EBRMemConfig.from_mem_dict(
        start_addr=RISCV_DV_START_ADDR,
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

    sim.add_sync_process(riscv_dv_sim_process(cpu))
    
    with sim.write_vcd("cpu.vcd"):
        sim.run()
    print("== Waveform dumped to cpu.vcd file")

