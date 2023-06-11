#!/usr/bin/env python3

from dataclasses import dataclass

from amaranth.sim import Simulator

from mtkcpu.cpu.cpu import MtkCpu, EBRMemConfig
from mtkcpu.utils.tests.dmi_utils import DMI_Monitor, dmi_op_wait_for_success
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


def yield_few_ticks():
    for _ in range(10):
        yield

def grp_to_dmi_access_register_regno(reg: int) -> int:
    assert reg in range(32)
    return 0x1000 + reg

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

        yield cpu.debug.jtag.ir.eq(JtagIR.DMI)
        yield cpu.debug.HALT.eq(1)
        
        yield_few_ticks()

        # Write pattern to DATA0, so that it becomes a payload for further register write.
        pattern = 0xdeadbeef

        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.DATA0)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
        yield dmi_monitor.cur_dmi_bus.data.eq(pattern)
        
        # Start the transaction.
        yield dmi_monitor.jtag_tap_dmi_bus.update.eq(1)

        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        # Note that we assume 'update' bit to go down after a single cycle.
        # The relevant logic is inside Debug Module.
        assert not (yield dmi_monitor.jtag_tap_dmi_bus.update)

        # Make sure that DATA0 does contain 'pattern'.
        data0 = yield cpu.debug.dmi_regs[DMIReg.DATA0].as_value()
        if data0 != pattern:
            raise ValueError(f"DATA0 read: expected {hex(pattern)}, got {hex(data0)}")
        
        # Reset the bus value.
        yield dmi_monitor.cur_dmi_bus.as_value().eq(0)

        # Make the Debug Module write DATA0 content to some CPU GPR, using 'Access Register' abstract command.
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.COMMAND)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
        yield dmi_monitor.cur_COMMAND.cmdtype.eq(COMMAND_Layout.AbstractCommandCmdtype.AccessRegister)
        
        # Fill the 'Access Register'-specific params.
        acc_reg = dmi_monitor.cur_COMMAND.control.ar
        yield acc_reg.regno.eq(grp_to_dmi_access_register_regno(1))
        yield acc_reg.write.eq(1)
        yield acc_reg.transfer.eq(1)
        yield acc_reg.aarsize.eq(AbstractCommandControl.AccessRegisterLayout.AARSIZE.BIT32)

        for _ in range(5):
            yield
        
        # Start the transaction.
        yield dmi_monitor.jtag_tap_dmi_bus.update.eq(1)

        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        yield_few_ticks()

        # Read GPR directly from CPU.
        # TODO - in future CPU should be abstract away, like "DMI_Monitor" abstracts away DM implementation.
        gpr_value = yield cpu.regs._array[1]
        
        if gpr_value != pattern:
            raise ValueError(f"GRP read: expected {hex(pattern)}, got {hex(gpr_value)}!")
        
        logging.info("GPR register write verified!")

    simulator.add_sync_process(process)

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