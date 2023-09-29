from pathlib import Path
import logging
from shutil import which
import pytest

from mtkcpu.utils.tests.utils import assert_jtag_test
from mtkcpu.units.debug.impl_config import TOOLCHAIN
from mtkcpu.global_config import Config

@pytest.mark.skip
def test_openocd_gdb():
    logging.info("JTAG test (with openocd and gdb)")

    # TODO: We really need setup&build support for setup stage, to install correct tools.
    openocd_executable = Config.git_root / ".." / "riscv-openocd" / "src" / "openocd"

    if not openocd_executable.exists():
        raise ValueError(f"openocd executable ({openocd_executable}) does not exists!")

    gdb_executable = f"{TOOLCHAIN}-gdb"

    if which(gdb_executable) is None:
        raise ValueError(f"gdb executable ({gdb_executable}) either not found or not eXecute permissions")
    
    assert_jtag_test(
        with_checkpoints=True,
        openocd_executable=openocd_executable,
        gdb_executable=Path(which(gdb_executable)),
    )

if __name__ == "__main__":
    # It helps when we use 'pytest.mark.skip', as there is no good workaround for that
    # (source: https://stackoverflow.com/questions/56078593/how-to-disable-skipping-a-test-in-pytest-without-modifying-the-code).
    test_openocd_gdb()
