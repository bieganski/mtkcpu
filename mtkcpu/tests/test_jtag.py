from pathlib import Path

from mtkcpu.utils.tests.utils import assert_jtag_test

import logging

def get_git_root() -> Path:
    """
    WARNING: not to be used inside package!
    """
    import subprocess
    process = subprocess.Popen("git rev-parse --show-toplevel", shell=True, stdout=subprocess.PIPE)
    stdout, _ = process.communicate()
    return Path(stdout.decode("ascii").strip())

def test_openocd_gdb():
    logging.info("JTAG test (with openocd and gdb)")

    openocd_executable = get_git_root() / "openocd_riscv" / "src" / "openocd"

    gdb_executable = get_git_root() / "xpack-riscv-none-embed-gcc-8.3.0-2.3" / "bin" / "riscv-none-embed-gdb"

    for x in openocd_executable, gdb_executable:
        if not x.exists():
            raise ValueError(f"{x} executable does not exists!")
    
    assert_jtag_test(
        timeout_cycles=1000, # TODO timeout not used
        with_checkpoints=True,
        openocd_executable=openocd_executable,
        gdb_executable=gdb_executable,
    )

if __name__ == "__main__":
    # If you need verbose output by default, invoke it directly instead of via pytest.
    test_openocd_gdb()
