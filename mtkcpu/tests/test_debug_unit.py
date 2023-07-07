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


@dmi_simulator
def test_dmi_abstract_command_read_write_gpr(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):

    def main_process():
        """
        Write some value to x1, wait, and read x1. Expect to read exactly initial value.
        """
        # Warmup, initial setup.
        yield from activate_DM_and_halt_via_dmi(dmi_monitor=dmi_monitor)

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
        yield from dmi_write_access_register_command(
            dmi_monitor=dmi_monitor,
            write=True,
            regno=gpr_to_dmi_access_register_regno(regno),
        )
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
        yield from dmi_write_access_register_command(
            dmi_monitor=dmi_monitor,
            write=False,
            regno=gpr_to_dmi_access_register_regno(regno),
        )
        yield from few_ticks(5)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        data0 = yield cpu.debug.dmi_regs[DMIReg.DATA0].as_value()
        if data0 != pattern:
            raise ValueError(f"DATA0 read: expected {hex(pattern)}, got {hex(data0)}")

        logging.info(f"Value read via DMI from DATA0 matches x{regno} content!")
    
    processes = [
        main_process,
        *error_monitors(dmi_monitor),
    ]

    for p in processes:
        simulator.add_sync_process(p)

    vcd_traces = [
        # *dmi_monitor.cur_COMMAND_r.fields.values(),
        cpu.debug.jtag.BAR,
        *dmi_monitor.cur_ABSTRACTCS_latched_r.fields.values(),
        cpu.debug.jtag.BAR,
    ]
    
    with simulator.write_vcd("temp.vcd", "temp.gtkw", traces=vcd_traces):
        simulator.run()


@dmi_simulator
def test_dmi_try_read_not_implemented_register(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):

    def main_process():
        """
        RV Debug Specs 1.0-STABLE
        3.15 Debug Module Registers

        When read, unimplemented or non-existent Debug Module DMI Registers return 0.
        Writing them has no effect.
        """

        # Warmup, initial setup.
        yield from few_ticks()
        yield from activate_DM_and_halt_via_dmi(dmi_monitor=dmi_monitor)

        from mtkcpu.units.debug.dmi_handlers import DMI_HANDLERS_MAP
        not_implemented_dmi_regs = [0x1, 0x2, 0x3]
        assert not [x for x in not_implemented_dmi_regs if x in DMI_HANDLERS_MAP]

        for dmi_reg in not_implemented_dmi_regs:
            logging.debug(f"Writing dummy value to non-existing DMI register at address {hex(dmi_reg)}")
            yield dmi_monitor.cur_dmi_bus.address.eq(dmi_reg)
            yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
            yield dmi_monitor.cur_dmi_bus.data.eq(0xdeadbeef)
            yield from few_ticks(5)
            yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
            dmi_op_wait_for_success(dmi_monitor)

        for dmi_reg in not_implemented_dmi_regs:
            logging.debug(f"Reading value from non-existing DMI register at address {hex(dmi_reg)}")
            yield dmi_monitor.cur_dmi_bus.address.eq(dmi_reg)
            yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.READ)
            yield from few_ticks(5)
            yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
            dmi_op_wait_for_success(dmi_monitor)
            data = yield dmi_monitor.cur_dmi_read_data
            if data != 0x0:
                raise ValueError(f"Expected data=0x0, got {hex(data)}")

    processes = [
        main_process,
        *error_monitors(dmi_monitor),
    ]
    
    for p in processes:
        simulator.add_sync_process(p)
        
    simulator.run()


@dmi_simulator
def test_core_halt_resume(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):

    def cpu_core_is_halted():
        return (yield cpu.running_state.halted)

    def main_process():
        """
        RV Debug specs 1.0-STABLE

        3.5 Run Control

        When a debugger writes 1 to haltreq, each selected hart's halt request bit is set. 
        When a running hart, or a hart just coming out of reset, sees its halt request bit high, 
        it responds by halting, deasserting its running signal, and asserting its halted signal. 
        Halted harts ignore their halt request bit.

        When a debugger writes 1 to resumereq, each selected hart's resume ack bit is cleared 
        and each selected, halted hart is sent a resume request. Harts respond by resuming, 
        clearing their halted signal, and asserting their running signal. At the end of this process
        the resume ack bit is set. These status signals of all selected harts are reflected in 
        allresumeack, anyresumeack, allrunning, and anyrunning. Resume requests are ignored by running harts.
        """
        from amaranth.sim import Settle
        yield Settle()

        halted = yield from cpu_core_is_halted()

        if halted:
            raise ValueError("Core halted from the very beginning!")

        yield from activate_DM_and_halt_via_dmi(dmi_monitor=dmi_monitor)

        # Check CPU signal directly first..
        halted = yield from cpu_core_is_halted()
        if not halted:
            raise ValueError("CPU was not halted after haltreq set!")

        # .. and via DMI
        yield from DMSTATUS_read(dmi_monitor=dmi_monitor)
        
        assert dmi_monitor.cur_dmi_read_data.shape() == unsigned(32)
        data_read_via_dmi = data.View(DMSTATUS_Layout, dmi_monitor.cur_dmi_read_data)
        def check_dmstatus_field_values(fields: Sequence[str], expected: int):
            for x in fields:
                val = yield getattr(data_read_via_dmi, x)
                if val != expected:
                    raise ValueError(f"dmstatus.{x}=={val}, expected {expected}")
        
        halted_expected_low = ["allrunning", "anyrunning", "allresumeack", "anyresumeack"]
        halted_expected_high = ["allhalted", "anyhalted"]
        
        yield from check_dmstatus_field_values(halted_expected_low, 0)
        yield from check_dmstatus_field_values(halted_expected_high, 1)
        
        yield from DMCONTROL_setup_basic_fields(dmi_monitor=dmi_monitor, dmi_op=DMIOp.WRITE)
        yield dmi_monitor.cur_DMCONTROL.haltreq.eq(0)
        yield dmi_monitor.cur_DMCONTROL.resumereq.eq(1)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from few_ticks(100)

        yield from DMSTATUS_read(dmi_monitor=dmi_monitor)

        yield from check_dmstatus_field_values(halted_expected_low, 1)
        yield from check_dmstatus_field_values(halted_expected_high, 0)
    
    processes = [
        main_process,
        *error_monitors(dmi_monitor),
        *informative_monitors(dmi_monitor),
    ]

    for p in processes:
        simulator.add_sync_process(p)

    vcd_traces = [
        cpu.just_halted,
        cpu.just_resumed,

        cpu.running_state_interface.haltreq,
        cpu.running_state_interface.haltack,
        cpu.running_state_interface.resumereq,
        cpu.running_state_interface.resumeack,

        cpu.running_state.halted,
    ]
        
    with simulator.write_vcd("halt.vcd", "halt.gtkw", traces=vcd_traces):
        simulator.run()

@dmi_simulator
def test_cmderr_clear(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):
    def main_process():
        yield from few_ticks()

        # NOTE: Below line is implementation specific!
        unimplemented_reg = 0x301

        # Try reading some unsupported CSR.
        yield from dmi_write_access_register_command(
            dmi_monitor=dmi_monitor,
            write=True,
            regno=unimplemented_reg,
        )
        yield from few_ticks(5)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from few_ticks()

        # Make sure CMDERR is 2 (meaning 'not supported').
        cmderr = yield dmi_monitor.cur_ABSTRACTCS_latched.cmderr
        if cmderr != ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED:
            raise ValueError(f"Expected cmderr to be {ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED}, got {cmderr} instead!")
    
        # Make sure that writing 0x0 won't clear the cmderr.
        # NOTE that 'cmderr' is the only writable field in 'abstractcs', so don't care about other fields.
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.ABSTRACTCS)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
        yield dmi_monitor.cur_dmi_bus.data.eq(0)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from few_ticks()

        new_cmderr = yield dmi_monitor.cur_ABSTRACTCS_latched.cmderr

        if new_cmderr != cmderr:
            raise ValueError(f"cmderr was expected not to change after 0x0 write (W1C), but it changed from {cmderr} to {new_cmderr}!")
    
        # Finally properly clear it.
        # Once again note that other fields are read-only.
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.ABSTRACTCS)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
        yield dmi_monitor.cur_dmi_bus.data.eq(0xFFFF_FFFF)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from few_ticks()

        cmderr = yield dmi_monitor.cur_ABSTRACTCS_latched.cmderr
        if cmderr != ABSTRACTCS_Layout.CMDERR.NO_ERR:
            raise ValueError(f"'cmderr' that is W1C field was not cleared after writing ones! It holds {cmderr} value instead.")
        

    processes = [
        main_process,
    ]
    
    for p in processes:
        simulator.add_sync_process(p)
        
    simulator.run()



# TODO
# Almost-duplicate of mtkcpu.utils.tests.utils.capture_write_transactions, that captures only EBR transactions,
# but heavily used, so cannot easily change it.
def bus_capture_write_transactions(cpu : MtkCpu, output_dict: dict):
    def f():
        yield Passive()
        gb = cpu.arbiter.generic_bus
        
        while(True):
            en = yield gb.en
            store = yield gb.store
            if en and store:
                data = yield gb.write_data
                addr = yield gb.addr
                output_dict[addr] = data
            yield
    return f

@dmi_simulator
def test_progbus_writes_to_bus(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):
    from mtkcpu.units.debug.impl_config import PROGBUFSIZE, PROGBUF_MMIO_ADDR
    assert PROGBUFSIZE > 0

    memory = dict()

    def main_process():
        yield from few_ticks()

        # Make sure that writing 0x0 won't clear the cmderr.
        # NOTE that 'cmderr' is the only writable field in 'abstractcs', so don't care about other fields.
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.PROGBUF0)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
        yield dmi_monitor.cur_dmi_bus.data.eq(0xdeadbeef)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from few_ticks(1000)

        assert len(memory) == 1
        (addr, val), = memory.items()
        assert addr == PROGBUF_MMIO_ADDR
        assert val == 0xdeadbeef
        
    
    def wtf():
        yield Passive()

        while True:
            val = yield cpu.debug_bus.ack
            if val:
                raise ValueError("ACK!")
            yield

    processes = [
        main_process,   
        bus_capture_write_transactions(cpu=cpu, output_dict=memory),
        wtf,
    ]
    
    for p in processes:
        simulator.add_sync_process(p)
        
    simulator.run()


if __name__ == "__main__":
    # import pytest
    # pytest.main(["-x", __file__])
    # test_dmi_try_read_not_implemented_register()
    # test_dmi_abstract_command_read_write_gpr()
    # test_core_halt_resume()
    # test_cmderr_clear()
    test_progbus_writes_to_bus()
    logging.critical("ALL TESTS PASSED!")



