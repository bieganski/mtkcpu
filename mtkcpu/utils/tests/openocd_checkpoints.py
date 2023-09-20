from typing import Optional, Callable

from mtkcpu.utils.tests.dmi_utils import DMI_Monitor, few_ticks
from mtkcpu.units.debug.types import AccessRegisterLayout, DMCONTROL_Layout, DMIReg, DMIOp

from amaranth.sim import Passive
from amaranth import Signal

def dmcontrol_haltreq_written(dmi_monitor: DMI_Monitor):
    def aux():
        yield Passive()
        yield
        
        # https://github.com/amaranth-lang/amaranth/issues/786
        haltreq_offset = DMCONTROL_Layout(Signal(32))._View__layout._fields["haltreq"].offset
        
        haltreq_write = _generic_dmi_bus_cmp(
            dmi_monitor=dmi_monitor,
            expected_op=DMIOp.WRITE,
            expected_addr=DMIReg.DMCONTROL,
            expected_value_check=lambda data: data & (1 << haltreq_offset),
        )
        
        while True:
            if (yield from haltreq_write()):
                # Found a match, return immediately.
                return
            # No match - try once again in next clock cycle.
            yield
    return aux


def _generic_dmi_bus_cmp(
        dmi_monitor: DMI_Monitor,
        expected_op: DMIOp,
        expected_addr: DMIReg,
        expected_value_check: Optional[Callable[[int], bool]],
        ) -> Callable[[], bool]:
    """
    returns True if Debug Bus matches in current clock cycle, False otherwise.

    For flexibility 'expected_value_check' can be either None 
    - then no check on 'data' will be performed, or a callable, to provide support for
    bit fields checking, casting as View etc.

    'expected_value_check' is to return True if the data matches expected value.
    """
    def aux() -> bool:
        op = yield dmi_monitor.cur_dmi_bus.op
        address = yield dmi_monitor.cur_dmi_bus.address

        if (op, address) != (expected_op, expected_addr):
            return False
        if expected_value_check is None:
            return True
        data = yield dmi_monitor.cur_dmi_bus.data
        return expected_value_check(data)
    
    return aux

def _wait_for_dmi_bus_change_skip_nop(
        dmi_monitor: DMI_Monitor,
):
    initial = yield dmi_monitor.cur_dmi_bus.as_value()
    while True:
        op = yield dmi_monitor.cur_dmi_bus.op
        if op == DMIOp.NOP:
            yield
            continue
        val = yield dmi_monitor.cur_dmi_bus.as_value()
        if val != initial:
            return
        yield

def progbuf_written_and_started(dmi_monitor: DMI_Monitor, progbuf_num: int, instr: Optional[int]):
    def aux():
        yield Passive()

        progbuf_cmp = _generic_dmi_bus_cmp(
            dmi_monitor=dmi_monitor,
            expected_op=DMIOp.WRITE,
            expected_addr=DMIReg.PROGBUF0 + progbuf_num,
            expected_value_check=lambda data: data == instr,
        )

        # https://github.com/amaranth-lang/amaranth/issues/786
        postexec_offset = AccessRegisterLayout(Signal(24))._View__layout._fields["postexec"].offset

        command_cmp = _generic_dmi_bus_cmp(
            dmi_monitor=dmi_monitor,
            expected_op=DMIOp.WRITE,
            expected_addr=DMIReg.COMMAND,
            expected_value_check=lambda data: data & (1 << postexec_offset),
        )

        while True:

            # Wait for PROFBUGx written with expected instruction.
            while not (yield from progbuf_cmp()): yield

            # Next (consecutive!) write is supposed to be COMMAND register, with 'postexec' bit set.
            yield from _wait_for_dmi_bus_change_skip_nop(dmi_monitor=dmi_monitor)

            if (yield from command_cmp()):
                break # success!

        # let the monitor processes print COMMAND params to stdout/stderr.
        yield from few_ticks()
            
    return aux

def examination_finished_with_hart_resume(dmi_monitor: DMI_Monitor):
    """
    openOCD tries to make initial target examination invisible - to achieve that it first
    reads initial halt/running state, then performs series of {halt/resume} requests, and finally
    restores initial state. RISC-V after reset deasserted is by default running, so openOCD leave it running as well.

    side NOTE: just after examination finishes, the openOCD is able to handle requests from GDB.
    """
    def aux():
        yield Passive()

                # https://github.com/amaranth-lang/amaranth/issues/786
        resumereq_offset = DMCONTROL_Layout(Signal(32))._View__layout._fields["resumereq"].offset
        dmactive_offset  = DMCONTROL_Layout(Signal(32))._View__layout._fields["dmactive"].offset
        
        resumereq_write = _generic_dmi_bus_cmp(
            dmi_monitor=dmi_monitor,
            expected_op=DMIOp.WRITE,
            expected_addr=DMIReg.DMCONTROL,
            expected_value_check=lambda data: data & (1 << resumereq_offset),
        )

        dmstatus_read = _generic_dmi_bus_cmp(
            dmi_monitor=dmi_monitor,
            expected_op=DMIOp.READ,
            expected_addr=DMIReg.DMSTATUS,
            expected_value_check=None,
        )

        dmcontrol_just_dmactive = _generic_dmi_bus_cmp(
            dmi_monitor=dmi_monitor,
            expected_op=DMIOp.WRITE,
            expected_addr=DMIReg.DMCONTROL,
            expected_value_check=lambda data: data == (1 << dmactive_offset),
        )

        while True:
            while not (yield from resumereq_write()): yield

            yield from _wait_for_dmi_bus_change_skip_nop(dmi_monitor=dmi_monitor)

            if not (yield from dmstatus_read()):
                continue

            yield from _wait_for_dmi_bus_change_skip_nop(dmi_monitor=dmi_monitor)

            if (yield from dmcontrol_just_dmactive()):
                break # success
        
        yield from few_ticks()
            
    return aux