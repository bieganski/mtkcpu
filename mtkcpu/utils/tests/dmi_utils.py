
from amaranth import Signal, Elaboratable
from amaranth.hdl import rec
from amaranth import Module, Cat, Signal
from amaranth.sim import Passive

from mtkcpu.units.debug.types import *
from mtkcpu.utils.misc import get_color_logging_object, get_members
from mtkcpu.cpu.cpu import MtkCpu

logging = get_color_logging_object()

def to_record(v: data.View) -> rec.Record:
    """
    For simulation, to properly display named slices of Views.
    Only till https://github.com/amaranth-lang/amaranth/issues/790 is resolved.
    """
    members : dict = data.Layout.cast(v._View__orig_layout).members
    return rec.Record(rec.Layout([x for x in members.items()]))

def record_view_connect_statements(r: rec.Record, v: data.View) -> list:
    members : dict = data.Layout.cast(v._View__orig_layout).members
    return [getattr(r, name).eq(getattr(v, name)) for name in members]


class DMI_Monitor(Elaboratable):
    def __init__(self, cpu: MtkCpu):
        self.cpu = cpu

        jtag_tap_dmi_bus = self.jtag_tap_dmi_bus = cpu.debug.jtag.regs[JtagIR.DMI]
        
        # TODO - typing annotations below are wrong, but IDE is happy.

        # JTAG tap's DMI bus, not yet latched by DM.
        self.cur_dmi_bus : IR_DMI_Layout   = data.View(IR_DMI_Layout,   jtag_tap_dmi_bus.w)
        self.cur_COMMAND : COMMAND_Layout  = data.View(COMMAND_Layout,  self.cur_dmi_bus.data)
        
        # latched by DM.
        self.cur_ABSTRACTCS_latched : ABSTRACTCS_Layout = data.View(ABSTRACTCS_Layout, cpu.debug.dmi_regs[DMIReg.ABSTRACTCS])

        self.prev_COMMAND : COMMAND_Layout = Signal.like(self.cur_COMMAND)
        self.prev_dmi_bus : IR_DMI_Layout  = Signal.like(self.cur_dmi_bus)
        
        self.error = Signal()

        # Records below are to be removed after https://github.com/amaranth-lang/amaranth/issues/790 is resolved.
        self.cur_COMMAND_r = to_record(self.cur_COMMAND)
        self.cur_ABSTRACTCS_latched_r = to_record(self.cur_ABSTRACTCS_latched)

    def elaborate(self, platform):
        m = Module()

        ############################################################################
        # Only till https://github.com/amaranth-lang/amaranth/issues/790 is resolved.
        records_views = [
            (self.cur_COMMAND_r, self.cur_COMMAND),
            (self.cur_ABSTRACTCS_latched_r, self.cur_ABSTRACTCS_latched),
        ]

        for r, v in records_views:
            m.d.comb += record_view_connect_statements(r, v)
        ############################################################################

        def _raise():
            m.d.sync += self.error.eq(1)

        cpu = self.cpu
        m.submodules.cpu = cpu

        sync, comb = m.d.sync, m.d.comb

        jtag_dr_update = cpu.debug.jtag.jtag_fsm_update_dr
        jtag_ir = cpu.debug.jtag.ir

        self.new_dmi_transaction = ((jtag_ir == JtagIR.DMI) & jtag_dr_update)

        # latch previous DMI op.
        with m.If(self.new_dmi_transaction):
            sync += [
                self.prev_dmi_bus.eq(self.cur_dmi_bus),
            ]

        access_register = COMMAND_Layout.AbstractCommandCmdtype.AccessRegister

        with m.If(self.cur_dmi_bus.address == DMIReg.COMMAND):
            with m.If(self.cur_COMMAND.cmdtype != access_register):
                _raise()
            
        return m

def monitor_cmderr(dmi_monitor: DMI_Monitor):
    def aux():
        yield Passive()

        while True:
            cmderr = yield dmi_monitor.cur_ABSTRACTCS_latched.cmderr
            if cmderr == ABSTRACTCS_Layout.CMDERR.OTHER:
                raise ValueError("cmderror OTHER detected! Probably not implemented scenario happened")
            if cmderr != ABSTRACTCS_Layout.CMDERR.NO_ERR:
                logging.warn(f"cmderr == {cmderr}")
            yield
    return aux

def print_dmi_transactions(dmi_monitor: DMI_Monitor):
    def aux():
        yield Passive()

        def print_fn(s: str):
            logging.info(s)
        
        while True:
            new_dmi_transaction = yield dmi_monitor.new_dmi_transaction
            if new_dmi_transaction:
                op   = yield dmi_monitor.cur_dmi_bus.op
                addr = yield dmi_monitor.cur_dmi_bus.address
                if op in [DMIOp.READ, DMIOp.WRITE]:
                    action = "reading" if op == DMIOp.READ else "writing"
                    try:
                        addr = DMIReg(addr)
                    except:
                        pass
                    print_fn(f"DMI: {action}, address: {addr!r}")

                    # if op == DMIOp.WRITE:  # XXX NOT YET TESTED.
                    acc_reg = dmi_monitor.cur_COMMAND.control.ar
                    regno = yield acc_reg.regno
                    write = yield acc_reg.write
                    transfer = yield acc_reg.transfer
                    aarsize = yield acc_reg.aarsize
                    if transfer:
                        action = "REG write" if write else "REG read"
                        logging.critical("shit detected")
                        for _ in range(50):
                            yield
                        raise ValueError(f"{action}, addr: {hex(regno)}")
                    
            yield
    return aux

def dmi_op_wait_for_success(dmi_monitor: DMI_Monitor, timeout: int = 40):
    """
    Check 'busy' and 'cmderr' fields in 'abstractcs'.
    Raises if 'cmderr' is nonzero, or if 'busy' is never high/is high for too long.
    """
    for i in range(timeout):
        busy = yield dmi_monitor.cur_ABSTRACTCS_latched.busy
        if busy:
            break
        yield
    else:
        raise ValueError(f"abstractcs.busy wasn't asserted during {timeout} cycles!")
    
    for i in range(i, timeout):
        busy = yield dmi_monitor.cur_ABSTRACTCS_latched.busy
        cmderr = yield dmi_monitor.cur_ABSTRACTCS_latched.cmderr

        if cmderr:
            raise ValueError(f"abstractcs.cmderr detected high, while expecting it to be low!")

        if not busy:
            logging.debug(f"DMI OP finished in {i} ticks.")
            break
        yield   
    else:
        raise ValueError("abstractcs.busy high for too long!")


def dmi_bus_reset(dmi_monitor: DMI_Monitor):
    yield dmi_monitor.cur_dmi_bus.as_value().eq(0)

def dmi_bus_trigger_transaction(dmi_monitor: DMI_Monitor):
    yield dmi_monitor.jtag_tap_dmi_bus.update.eq(1)

def grp_to_dmi_access_register_regno(reg: int) -> int:
    assert reg in range(32)
    return 0x1000 + reg

def dmi_write_access_register_command(
        dmi_monitor: DMI_Monitor,
        write: bool,
        regno: int,
        ):
    yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.COMMAND)
    yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
    yield dmi_monitor.cur_COMMAND.cmdtype.eq(COMMAND_Layout.AbstractCommandCmdtype.AccessRegister)

    regno = grp_to_dmi_access_register_regno(regno)
    acc_reg = dmi_monitor.cur_COMMAND.control.ar

    yield acc_reg.regno.eq(regno)
    yield acc_reg.write.eq(int(write))
    yield acc_reg.transfer.eq(1)
    yield acc_reg.aarsize.eq(AbstractCommandControl.AccessRegisterLayout.AARSIZE.BIT32)

def dmi_write_data0(
        dmi_monitor: DMI_Monitor,
        value: int
        ):
    yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.DATA0)
    yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
    yield dmi_monitor.cur_dmi_bus.data.eq(value)
