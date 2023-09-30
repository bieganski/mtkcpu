from pathlib import Path
import logging
from shutil import which
import pytest

from mtkcpu.utils.tests.utils import assert_jtag_test
from mtkcpu.units.debug.impl_config import TOOLCHAIN

def test_openocd_gdb():
    logging.info("JTAG test (with openocd and gdb)")

    gdb_executable = f"{TOOLCHAIN}-gdb"
    openocd_executable = "openocd"

    for x in [openocd_executable, gdb_executable]:
        if which(x) is None:
            raise ValueError(f"executable {x} either not found or lacks eXecute permissions")
    
    assert_jtag_test(
        with_checkpoints=True,
        openocd_executable=Path(which(openocd_executable)),
        gdb_executable=Path(which(gdb_executable)),
    )

if __name__ == "__main__":
    # It helps when we use 'pytest.mark.skip', as there is no good workaround for that
    # (source: https://stackoverflow.com/questions/56078593/how-to-disable-skipping-a-test-in-pytest-without-modifying-the-code).
    test_openocd_gdb()
