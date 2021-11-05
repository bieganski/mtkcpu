from mtkcpu.utils.tests.utils import component_testbench, ComponentTestbenchCase

from mtkcpu.units.loadstore import MemoryArbiter, PriorityEncoder
TESTBENCHES = [
    ComponentTestbenchCase(
        name="MemoryArbiter",
        component_type=MemoryArbiter
    ),
    ComponentTestbenchCase(
        name="PriorityEncoder",
        component_type=PriorityEncoder
    ),
]

@component_testbench(TESTBENCHES)
def test_tb(_):
    pass
