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


@pytest.mark.skip
def test_virtual_mem():
    # from mtkcpu.utils.tests.vm_tb import basic_vm_test # XXX
    from vm_tb import basic_vm_test
    basic_vm_test()

@component_testbench(TESTBENCHES)
def test_tb(_):
    pass

@cpu_testbench(CPU_TESTBENCHES)
def test_tb_cpu(_):
    pass