#!/usr/bin/env python3

from amaranth.sim import Simulator

from mtkcpu.cpu.cpu import MtkCpu, EBRMemConfig
from mtkcpu.utils.tests.utils import DMI_Monitor
from mtkcpu.units.debug.types import *
from dataclasses import dataclass

@dataclass
class DebugUnitSimulationContext:
    cpu: MtkCpu
    dmi_monitor: DMI_Monitor
    simulator: Simulator

def create_simulator() -> DebugUnitSimulationContext:
    cpu = MtkCpu(
        mem_config=EBRMemConfig(
            mem_size_words=1000,
            mem_content_words=None,
            mem_addr=0xA000,
            simulate=False,
        ),
        with_debug=True,
    )

    dmi_monitor = DMI_Monitor(cpu=cpu)

    simulator = Simulator(fragment=dmi_monitor)
    simulator.add_clock(1e-6)

    return DebugUnitSimulationContext(
        cpu=cpu,
        dmi_monitor=dmi_monitor,
        simulator=simulator,
    )

def dmi_simulator(f):
    def aux(*args, **kwargs):
        assert not args and not kwargs
        context = create_simulator()
        simulator = context.simulator
        cpu = context.cpu
        dmi_monitor = context.dmi_monitor
        from inspect import signature
        names, types = zip(*[(x.name, x.annotation) for x in signature(f).parameters.values()])
        expected_types = [Simulator, MtkCpu, DMI_Monitor]
        if len(types) != 3:
            raise NotImplementedError()
        assert all([x == y for x, y in zip(types[:3], expected_types)])
        f(simulator, cpu, dmi_monitor)
    return aux


def yield_few_ticks():
    for _ in range(10):
        yield

def grp_to_dmi_access_register_regno(reg: int) -> int:
    assert reg in range(32)
    return 0x1000 + reg

def dmi_op_wait_for_success(dmi_monitor: DMI_Monitor, timeout: int = 40):
    # Check 'busy' and 'cmderr' fields in 'abstractcs'.
    for i in range(timeout):
        busy = yield dmi_monitor.cur_ABSTRACTCS.busy
        if busy:
            break
        yield
    else:
        raise ValueError("abstractcs.busy was not set high!")
    
    for _ in range(i, timeout):
        busy = yield dmi_monitor.cur_ABSTRACTCS.busy
        cmderr = yield dmi_monitor.cur_ABSTRACTCS.cmderr

        if cmderr:
            raise ValueError(f"abstractcs.cmderr detected high, while expecting it to be low!")

        if not busy:
            break
    else:
        raise ValueError("abstractcs.busy high for too long!")

@dmi_simulator
def test_dmi(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):
    context = create_simulator()

    simulator = context.simulator
    cpu = context.cpu
    dmi_monitor = context.dmi_monitor
    
    def process():
        """
        Write some value to x1, wait, and read x1. Expect to read exactly initial value.
        """
        # Warmup.
        yield_few_ticks()

        # Write pattern to DATA0, so that it becomes a payload for further register write.
        pattern = 0xdeadbeef
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.DATA0)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
        yield dmi_monitor.cur_dmi_bus.data.eq(pattern)

        dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        # Make the Debug Module write DATA0 content to some CPU GPR.
        dmi_x1_regno = grp_to_dmi_access_register_regno(1)
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.COMMAND)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
        yield dmi_monitor.cur_COMMAND.cmdtype.eq(COMMAND_Layout.AbstractCommandCmdtype.AccessRegister)
        yield dmi_monitor.cur_AR.regno.eq(dmi_x1_regno)
        yield dmi_monitor.cur_AR.write.eq(1)
        yield dmi_monitor.cur_AR.transfer.eq(1)
        yield dmi_monitor.cur_AR.aarsize.eq(AccessRegisterLayout.AARSIZE.BIT32)

        dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        # TODO - set DMI bits low when success found...

        # Read CPU GPR.
        gpr_value = yield cpu.regs._array[1]
        
        if gpr_value != pattern:
            raise ValueError(f"Expected to read {hex(pattern)}, got {hex(gpr_value)}!")
        else:
            raise ValueError("GPR OK!")

    simulator.add_sync_process(process)
    
    with simulator.write_vcd("temp.vcd"):
        simulator.run()


if __name__ == "__main__":
    # import pytest
    # pytest.main(["-x", __file__])
    test_dmi()