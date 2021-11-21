from pathlib import Path
from mtkcpu.utils.tests.utils import component_testbench, ComponentTestbenchCase, CpuTestbenchCase, cpu_testbench
from mtkcpu.units.loadstore import MemoryArbiter
from mtkcpu.units.mmio.gpio import GPIO_Wishbone

TESTBENCHES = [
    ComponentTestbenchCase(
        name="MemoryArbiter",
        component_type=MemoryArbiter
    ),
    ComponentTestbenchCase(
        name="GPIO_Wishbone",
        component_type=GPIO_Wishbone
    ),
]

CPU_TESTBENCHES = [
    # CpuTestbenchCase(
    #     name="GPIO LED C++",
    #     elf_path=Path("sw/blink_led/build/blink_led.elf"),
    #     try_compile=True
    # ),
    CpuTestbenchCase(
        name="UART C++",
        elf_path=Path("sw/uart_tx/build/uart_tx.elf"),
        try_compile=True
    ),
]

# @component_testbench(TESTBENCHES)
# def test_tb(_):
#     pass

@cpu_testbench(CPU_TESTBENCHES)
def test_tb(_):
    pass