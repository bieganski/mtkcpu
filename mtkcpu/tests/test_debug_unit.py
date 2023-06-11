#!/usr/bin/env python3

from dataclasses import dataclass

from amaranth.sim import Simulator

from mtkcpu.cpu.cpu import MtkCpu, EBRMemConfig
from mtkcpu.utils.tests.dmi_utils import *
from mtkcpu.units.debug.types import *
from mtkcpu.utils.misc import get_color_logging_object


logging = get_color_logging_object()

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


def few_ticks(n=10):
    for _ in range(n):
        yield

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

    def cmderr_monitor():
        yield Passive()
        while True:
            cmderr = yield cpu.debug.controller.command_err
            if cmderr == ABSTRACTCS_Layout.CMDERR.OTHER:
                raise ValueError("XXX")
            if cmderr != ABSTRACTCS_Layout.CMDERR.NO_ERR:
                logging.warn(f"cmderr == {cmderr}")
            yield
    
    def main_process():
        """
        Write some value to x1, wait, and read x1. Expect to read exactly initial value.
        """
        # Warmup, initial setup.
        yield from few_ticks()
        yield cpu.debug.jtag.ir.eq(JtagIR.DMI)
        yield cpu.debug.HALT.eq(1)
        yield from few_ticks()

        # Write pattern to DATA0, so that it becomes a payload for further register write.
        # As a result, 'pattern' will be written to 'x1' GPR.
        pattern, regno = 0xdeadbeef, 1
        
        logging.info(f"DMI: Writing {hex(pattern)} to DATA0..")
        yield from dmi_write_data0(dmi_monitor=dmi_monitor, value=pattern)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        # Note that we assume 'update' bit to go down after a single cycle.
        # The relevant logic is expected to be inside Debug Module.
        assert not (yield dmi_monitor.jtag_tap_dmi_bus.update)

        # Make sure that DATA0 does contain 'pattern'.
        data0 = yield cpu.debug.dmi_regs[DMIReg.DATA0].as_value()
        if data0 != pattern:
            raise ValueError(f"DATA0 read: expected {hex(pattern)}, got {hex(data0)}")
        
        # Reset the bus value.
        yield from dmi_bus_reset(dmi_monitor=dmi_monitor)

        # Make the Debug Module write DATA0 content to some CPU GPR, using 'Access Register' abstract command.
        logging.info(f"DMI: Writing DATA0 to x{regno}..")
        yield from dmi_write_access_register_command(dmi_monitor=dmi_monitor, write=True, regno=regno)
        yield from few_ticks(5)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)
        yield from few_ticks()

        # Read GPR directly from CPU.
        # TODO - in future CPU should be abstract away, like "DMI_Monitor" abstracts away DM implementation.
        gpr_value = yield cpu.regs._array[1]
        if gpr_value != pattern:
            raise ValueError(f"GRP read: expected {hex(pattern)}, got {hex(gpr_value)}!")
        
        logging.info(f"{hex(pattern)} found in x{regno}!")
        logging.info("Trying to read it via DMI as well..")

        # Make sure that the 'pattern' that we will try to read in a moment
        # is not a remnant after previous op.
        antipattern = pattern // 2
        logging.info(f"DMI: Clobbering DATA0 with {hex(antipattern)}..")
        yield from dmi_bus_reset(dmi_monitor=dmi_monitor)
        yield from dmi_write_data0(dmi_monitor=dmi_monitor, value=antipattern)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)
        yield from few_ticks()
        data0 = yield cpu.debug.dmi_regs[DMIReg.DATA0].as_value()
        if data0 != antipattern:
            raise ValueError(f"DATA0 Clobbering failed: Written {antipattern}, detected {data0} instead!")

        # Now when we clobbered DATA0, read 'x1' to DATA0 and compare with 'pattern'.
        logging.info(f"DMI: Reading x{regno} to DATA0..")
        yield from dmi_bus_reset(dmi_monitor=dmi_monitor)
        yield from dmi_write_access_register_command(dmi_monitor=dmi_monitor, write=False, regno=regno)
        yield from few_ticks(5)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        data0 = yield cpu.debug.dmi_regs[DMIReg.DATA0].as_value()
        if data0 != pattern:
            raise ValueError(f"DATA0 read: expected {hex(pattern)}, got {hex(data0)}")

        logging.info(f"Value read via DMI from DATA0 matches x{regno} content!")

    for p in [main_process, cmderr_monitor]:
        simulator.add_sync_process(p)

    vcd_traces = [
        # *dmi_monitor.cur_COMMAND_r.fields.values(),
        cpu.debug.jtag.BAR,
        *dmi_monitor.cur_ABSTRACTCS_latched_r.fields.values(),
        cpu.debug.jtag.BAR,
    ]
    
    with simulator.write_vcd("temp.vcd", "temp.gtkw", traces=vcd_traces):
        simulator.run()


if __name__ == "__main__":
    # import pytest
    # pytest.main(["-x", __file__])
    test_dmi()