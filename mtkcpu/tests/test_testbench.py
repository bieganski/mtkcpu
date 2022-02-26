import pytest
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

# TODO 'try_compile' doesn't work well - instead we keep already compiled ELFs 
# inside tests/tb_assets directory. It's because mtkCPU installed via 'pip3 install' 
# command doesn't include sw/ directory, thus cannot build it.
CPU_TESTBENCHES = [
    CpuTestbenchCase(
        name="GPIO LED C++",
        sw_project="blink_led",
        try_compile=False
    ),
    CpuTestbenchCase(
        name="UART C++",
        sw_project="uart_tx",
        try_compile=False
    ),
]

# All tests here are marked 'skipped'. This is because mtkcpu
# can be used either by repository download or in 
# a library mode (a wheel, only with Python code). As a library it doens't have 
# copy of sw/ directory, that contains sources needed to generate
# .elf files, used by simulation code.

@pytest.mark.skip
def test_virtual_mem():
    from mtkcpu.utils.tests.vm_tb import basic_vm_test
    basic_vm_test()

@pytest.mark.skip
@component_testbench(TESTBENCHES)
def test_tb(_):
    pass

@pytest.mark.skip
@cpu_testbench(CPU_TESTBENCHES)
def test_tb_cpu(_):
    pass