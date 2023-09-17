from pathlib import Path
import logging

import pytest

from mtkcpu.utils.tests.utils import assert_jtag_test


def get_git_root() -> Path:
    """
    WARNING: not to be used inside package!
    """
    import subprocess
    process = subprocess.Popen("git rev-parse --show-toplevel", shell=True, stdout=subprocess.PIPE)
    stdout, _ = process.communicate()
    return Path(stdout.decode("ascii").strip())

@pytest.mark.skip
def test_openocd_gdb():
    logging.info("JTAG test (with openocd and gdb)")

    # openocd_executable = get_git_root() / "openocd_riscv" / "src" / "openocd"
    # TODO https://github.com/bieganski/mtkcpu/issues/30
    # Needs setup&build support for setup stage, to install correct tools.
    openocd_executable = get_git_root() / ".." / "riscv-openocd" / "src" / "openocd"

    gdb_executable = get_git_root() / "xpack-riscv-none-embed-gcc-8.3.0-2.3" / "bin" / "riscv-none-embed-gdb"

    for x in openocd_executable, gdb_executable:
        if not x.exists():
            raise ValueError(f"{x} executable does not exists!")
    
    assert_jtag_test(
        with_checkpoints=True,
        openocd_executable=openocd_executable,
        gdb_executable=gdb_executable,
    )

if __name__ == "__main__":
    # It helps when we use 'pytest.mark.skip', as there is no good workaround for that
    # (source: https://stackoverflow.com/questions/56078593/how-to-disable-skipping-a-test-in-pytest-without-modifying-the-code).
    test_openocd_gdb()
