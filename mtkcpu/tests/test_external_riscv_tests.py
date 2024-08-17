#!/usr/bin/env python3

from pathlib import Path
import logging
import pytest
from glob import glob

from mtkcpu.cli.top import get_board_cpu, sim
from mtkcpu.cpu.priv_isa import TrapCause
from mtkcpu.utils.common import CODE_START_ADDR
from mtkcpu.cpu.cpu import CPU_Config

@pytest.mark.skip
def sim_riscv_tests(elf_path: Path, verbose: bool, timeout_cycles: int = 10_000):

    cpu_config=CPU_Config(with_debug=True, dev_mode=False, with_virtual_memory=True, pc_reset_value=CODE_START_ADDR)
    cpu = get_board_cpu(elf_path=elf_path, cpu_config=cpu_config, num_bytes=None)
    
    def end_of_sim():
        # active process!
        mcause = cpu.csr_unit.mcause.as_view()
        yield

        for i in range(timeout_cycles):
            if not (is_trap := (yield cpu.main_fsm.ongoing("TRAP"))):
                yield
                continue
            is_irq = yield mcause.interrupt
            cause = yield mcause.ecode
            if (not is_irq) and (cause == TrapCause.ECALL_FROM_U):
                # 'syscall' invoked - sample return code.
                # see https://github.com/riscv-software-src/riscv-tests/issues/471 for magic numbers below.
                syscall_nr = yield cpu.regs._array[17] # a7
                return_value = yield cpu.regs._array[10] # a0
                assert syscall_nr == 93
                if return_value:
                    raise ValueError(f"failure: 'ecall' exit code: {return_value}")
                else:
                    logging.info(f"success! 'ecall' in cycle {i} exit code 0")
                return
            yield
        else:
            raise RuntimeError(f"timeout! sim did not finish after {timeout_cycles} cycles!")

    user_processes = [end_of_sim]

    if verbose:
        from mtkcpu.utils.tests.dmi_utils import bus_capture_write_transactions, monitor_pc_and_main_fsm
        user_processes.append(bus_capture_write_transactions(cpu=cpu, output_dict=dict()))
        # user_processes.append(monitor_pc_and_main_fsm(cpu=cpu, wait_for_first_haltreq=False))

    sim(
        cpu=cpu,
        user_processes=user_processes,
        verbose=verbose,
        # regs_verbose=["a10", "gp"],
        with_uart=False,
    )

if __name__ == "__main__":

    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("riscv_tests_binaries_dir", type=Path)
    dir: Path = parser.parse_args().riscv_tests_binaries_dir

    if not dir.exists():
        raise RuntimeError(f"{dir} does not exist!")

    if not dir.resolve().is_dir():
        raise RuntimeError(f"{dir} is not a valid directory!")

    # see https://github.com/bieganski/mtkcpu/issues/74
    user_excluded = ["rv32ui-p-ma_data"]

    test_paths = [x for x in dir.glob("rv32ui-p*") if not str(x).endswith(".dump") and not Path(x).name in user_excluded]

    if not test_paths:
        raise RuntimeError("No input files to test!")

    print("Testing following files:", ", ".join([x.name for x in test_paths]))

    for p in test_paths:
        logging.info(f"starting {p}")
        sim_riscv_tests(elf_path=p, verbose=False, timeout_cycles=10_000)
