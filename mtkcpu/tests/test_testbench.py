from mtkcpu.utils.tests.utils import component_testbench, ComponentTestbenchCase

from mtkcpu.units.loadstore import MemoryArbiter, GPIO_Wishbone
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

@component_testbench(TESTBENCHES)
def test_tb(_):
    pass
