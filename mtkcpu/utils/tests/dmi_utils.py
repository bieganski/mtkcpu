
from amaranth import Signal, Elaboratable
from amaranth.hdl import rec
from amaranth import Module, Cat, Signal
from amaranth.sim import Passive

from mtkcpu.units.debug.types import *
from mtkcpu.utils.misc import get_color_logging_object, get_members
from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.units.debug.types import DMI_reg_kinds

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
        self.cur_dmi_bus   : IR_DMI_Layout     = data.View(IR_DMI_Layout,   jtag_tap_dmi_bus.w)
        self.cur_COMMAND   : COMMAND_Layout    = data.View(COMMAND_Layout,  self.cur_dmi_bus.data)
        self.cur_DMCONTROL : DMCONTROL_Layout  = data.View(DMCONTROL_Layout,  self.cur_dmi_bus.data)

        self.cur_dmi_read_data : Signal = jtag_tap_dmi_bus.r.data

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

        prev_cmderr = None
        while True:
            cmderr = yield dmi_monitor.cur_ABSTRACTCS_latched.cmderr
            if cmderr == ABSTRACTCS_Layout.CMDERR.OTHER:
                raise ValueError("cmderror OTHER detected! Probably not implemented scenario happened")
            if cmderr != ABSTRACTCS_Layout.CMDERR.NO_ERR and prev_cmderr != cmderr:
                logging.warn(f"cmderr == {cmderr}")
            prev_cmderr = cmderr
            yield
    return aux

def monitor_cpu_dm_if_error(dmi_monitor: DMI_Monitor):
    def aux():
        yield Passive()

        while True:
            err = yield dmi_monitor.cpu.running_state_interface.error_sticky
            if err:
                raise ValueError("CpuRunningStateExternalInterface misuse detected!")
            yield
    return aux


def _bin(value: int) -> str:
    return '_'.join(format((value << i & 0xff00_0000) >> 24, '08b') for i in range(0, 25, 8))

def debug_inspect_applied_struct(struct: data.Struct, val: int) -> str:
    """
    It has some limitations:

    * only data.Struct supported (no data.Union)
    * works only with unsigned or amaranth.lib.enum.Enum.
    * ... but it does support recursive layouts.
    """
    from amaranth import Shape
    from amaranth.lib import enum, data

    if hasattr(struct, "_AggregateMeta__layout"):
        # TODO Idon't feel like I understand logic between layouts/views, so that
        # if statement is probably redundant.
        assert struct._AggregateMeta__layout == struct._View__layout
        layout = struct._AggregateMeta__layout
    else:
        if isinstance(struct, data.View):
            layout = data.Layout.of(struct)
        elif isinstance(struct, data._AggregateMeta):
            layout = data.Layout.of(struct)
        elif isinstance(struct, data.StructLayout):
            layout = struct
        else:
            raise ValueError(f"type of @param struct={struct} <{type(struct)}> not supported!")

    if not hasattr(layout, "members"):
        raise ValueError(f"{struct}, {layout}, {type(struct)}, {type(layout)}")

    lst = []
    for name, shape in layout.members.items():
        if isinstance(shape, Shape):
            pass
        elif isinstance(shape, enum.EnumMeta):
            shape = shape.as_shape()
        elif isinstance(shape, data._AggregateMeta):
            # nested data.Struct - do a recursive call.
            recursive_struct = shape.as_shape()
            recursive_res = debug_inspect_applied_struct(struct=recursive_struct, val=val)
            lst.append(f"[ {recursive_res} ]")
            val >>= recursive_struct.size
            continue
        else:
            raise ValueError(f"Unknown shape {shape} (of type {type(shape)} )")

        assert isinstance(shape, Shape)
        assert not shape.signed
        chunk = val & ((1 << shape.width) - 1)
        val >>= shape.width
        lst.append(f"{name}={hex(chunk)}")

    res = f"{struct.__class__}: {', '.join(reversed(lst))}"
    return res

def print_dmi_transactions(dmi_monitor: DMI_Monitor):
    def aux():
        yield Passive()

        def print_fn(s: str):
            logging.info(s)
        
        last_data0 = None
        while True:
            new_dmi_transaction = yield dmi_monitor.new_dmi_transaction
            if new_dmi_transaction:
                op   = yield dmi_monitor.cur_dmi_bus.op
                addr = yield dmi_monitor.cur_dmi_bus.address
                value = yield dmi_monitor.cur_dmi_bus.data
                if op in [DMIOp.READ, DMIOp.WRITE]:
                    action = "reading" if op == DMIOp.READ else "writing"
                    try:
                        struct, reg_dump = None, None
                        addr = DMIReg(addr)
                        struct = dmi_monitor.cpu.debug.dmi_regs[addr]
                    except Exception as e:
                        print_fn(f"Either unknown DMI reg {addr} or not registered in DMI_reg_kinds.")
                    
                    if op == DMIOp.WRITE and struct is not None:
                        reg_dump = debug_inspect_applied_struct(struct, value)

                    print_fn(f"DMI: {action}, address: {addr!r}, value: {hex(value)} aka {_bin(value)}, dump {reg_dump}")

                    if op == DMIOp.READ:
                        if struct is None:
                            print_fn(f"Skipping waiting for DMI READ to complete "
                                     "as DMI REG {addr} is not implemented, so no dump can be created.")
                            yield
                            continue
                        timeout = 1000
                        for _ in range(timeout):
                            dr_capture = yield dmi_monitor.cpu.debug.jtag.jtag_fsm_capture_dr
                            if dr_capture:
                                break
                            else:
                                yield
                        else:
                            raise ValueError(f"After DMI READ testbenched expected DR capture to happen in {timeout} cycles, but it didn't happen.")

                        # TODO - the 2 bits offset is because 'dr' is 41 bits (7 addr, 32 data, 2 op_type)
                        dr = (yield dmi_monitor.cpu.debug.jtag.dr) >> 2
                        reg_dump = debug_inspect_applied_struct(struct, dr)
                        logging.warn(f"DMI READ RESPONSE to address: {addr!r}, value: {hex(dr)} aka {_bin(dr)}, dump {reg_dump}")
                        continue

                    assert op != DMIOp.READ

                    if addr == DMIReg.DATA0 and op == DMIOp.WRITE:
                        last_data0 = value
                        logging.critical(f">>>                                             SETTING DATA0 to {hex(last_data0)}")

                    if addr == DMIReg.COMMAND:
                        assert op == DMIOp.WRITE
                        acc_reg = dmi_monitor.cur_COMMAND.control
                        regno = yield acc_reg.regno
                        write = yield acc_reg.write
                        transfer = yield acc_reg.transfer
                        aarsize = yield acc_reg.aarsize
                        if transfer:
                            if write:
                                logging.critical(f"DMI WRITE, addr: {hex(regno)}, DATA0: {hex(last_data0)}")
                            else:
                                logging.critical(f"DMI READ, addr: {hex(regno)}")
                                
                    
                    if addr == DMIReg.DMCONTROL and op == DMIOp.WRITE:
                        haltreq = yield dmi_monitor.cur_DMCONTROL.haltreq
                        resumereq = yield dmi_monitor.cur_DMCONTROL.resumereq
                        cpu_dmactive = yield dmi_monitor.cpu.debug.dmi_regs[DMIReg.DMCONTROL].dmactive
                        if (not cpu_dmactive) and (haltreq or resumereq):
                            raise ValueError(f"Likely a bug in CPU implementation: Attempt to (haltreq={haltreq}, resumereq={resumereq}) when cpu's dmactive=0!")
                        cpu_halted = yield dmi_monitor.cpu.running_state.halted
                        if haltreq:
                            if (not cpu_dmactive) or cpu_halted:
                                raise ValueError(f"Likely a bug in CPU implementation: Attempt to haltreq when cpu's dmactive={cpu_dmactive}, cpu_running_state.halted={cpu_halted}!")                    
                    
                    from riscvmodel.code import decode
                    if addr in [DMIReg.PROGBUF0 + i for i in range(16)] and op == DMIOp.WRITE:
                        try:
                            ins_str = f"{decode(value)}  <{hex(value)}>"
                        except Exception:
                            ins_str = f"Unknown: {hex(value)}"
                        logging.critical(f"PROGBUF{addr - DMIReg.PROGBUF0} write: {ins_str}")
            yield
    return aux

def dmi_op_wait_for_cmderr(dmi_monitor: DMI_Monitor, expected_cmderr: int, timeout: int = 40):
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
        raise ValueError(f"dmi_op_wait_for_cmderr: abstractcs.busy wasn't asserted during {timeout} cycles!")
    
    for i in range(i, timeout):
        busy = yield dmi_monitor.cur_ABSTRACTCS_latched.busy
        cmderr = yield dmi_monitor.cur_ABSTRACTCS_latched.cmderr

        if not busy:
            logging.debug(f"DMI OP finished in {i} ticks.")

            if cmderr != expected_cmderr:
                raise ValueError(f"Expected cmderr {expected_cmderr}, got {cmderr}")
            break
        yield   
    else:
        raise ValueError("dmi_op_wait_for_cmderr: abstractcs.busy high for too long!")


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
        raise ValueError(f"dmi_op_wait_for_success: abstractcs.busy wasn't asserted during {timeout} cycles!")
    
    for i in range(i, timeout):
        busy = yield dmi_monitor.cur_ABSTRACTCS_latched.busy
        cmderr = yield dmi_monitor.cur_ABSTRACTCS_latched.cmderr

        if cmderr:
            raise ValueError(f"dmi_op_wait_for_success: detected nonzero0 abstractcs.cmderr ({cmderr})!")

        if not busy:
            logging.debug(f"DMI OP finished in {i} ticks.")
            break
        yield   
    else:
        raise ValueError("dmi_op_wait_for_success: abstractcs.busy high for too long!")


def dmi_bus_reset(dmi_monitor: DMI_Monitor):
    yield dmi_monitor.cur_dmi_bus.as_value().eq(0)

def dmi_bus_trigger_transaction(dmi_monitor: DMI_Monitor):
    """
    Note that in jtag.py there is some logic that deasserts 'update' bit in every single cycle,
    So that we don't have to take care of deasserting it in simulation.
    """
    yield dmi_monitor.jtag_tap_dmi_bus.update.eq(1)

def gpr_to_dmi_access_register_regno(reg: int) -> int:
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
    
    acc_reg = dmi_monitor.cur_COMMAND.control

    yield acc_reg.regno.eq(regno)
    yield acc_reg.write.eq(int(write))
    yield acc_reg.transfer.eq(1)
    yield acc_reg.aarsize.eq(AccessRegisterLayout.AARSIZE.BIT32)

def dmi_write_data0(
        dmi_monitor: DMI_Monitor,
        value: int
        ):
    yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.DATA0)
    yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
    yield dmi_monitor.cur_dmi_bus.data.eq(value)

def error_monitors(dmi_monitor: DMI_Monitor):
    return [
        monitor_cmderr(dmi_monitor),
        monitor_cpu_dm_if_error(dmi_monitor),
    ]

def informative_monitors(dmi_monitor: DMI_Monitor):
    return [
        monitor_cpu_and_dm_state(dmi_monitor=dmi_monitor),
    ]

def few_ticks(n=10):
    for _ in range(n):
        yield

def DMCONTROL_setup_basic_fields(dmi_monitor: DMI_Monitor, dmi_op: DMIOp):
    assert dmi_op in [DMIOp.READ, DMIOp.WRITE]
    yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.DMCONTROL)
    yield dmi_monitor.cur_dmi_bus.op.eq(dmi_op)
    yield dmi_monitor.cur_DMCONTROL.dmactive.eq(1)

def DMSTATUS_read(dmi_monitor: DMI_Monitor):
    yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.DMSTATUS)
    yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.READ)
    yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
    yield from few_ticks(100)


def activate_DM_and_halt_via_dmi(dmi_monitor: DMI_Monitor):
    # Only assert 'dmactive'.
    yield from DMCONTROL_setup_basic_fields(dmi_monitor=dmi_monitor, dmi_op=DMIOp.WRITE)
    yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
    yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor, timeout=20)

    # Once 'dmactive' is hight, select hart 0 and halt it.
    yield from DMCONTROL_setup_basic_fields(dmi_monitor=dmi_monitor, dmi_op=DMIOp.WRITE)
    yield dmi_monitor.cur_DMCONTROL.haltreq.eq(1)
    yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
    yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor, timeout=20)

def monitor_cpu_and_dm_state(dmi_monitor: DMI_Monitor):
    def aux():
        yield Passive()

        prev_cpu_state = None
        prev_dmactive = None
        while True:
            dmactive = yield dmi_monitor.cpu.debug.dmi_regs[DMIReg.DMCONTROL].dmactive
            if dmactive != prev_dmactive:
                repr = "active" if dmactive else "inactive"
                note = "from initial" if prev_dmactive is None else ""
                logging.info(f"DM changed state {note} to {repr}")
            prev_dmactive = dmactive
            
            cpu_state = yield dmi_monitor.cpu.running_state.halted
            if cpu_state != prev_cpu_state:
                repr = "halted" if cpu_state else "running"
                note = "from initial" if prev_cpu_state is None else ""
                logging.info(f"CPU changed state {note} to {repr}")
            prev_cpu_state = cpu_state

            yield
    return aux


def monitor_halt_or_resume_req_get_ack(dmi_monitor: DMI_Monitor, timeout_ticks: int = 20):
    def aux():
        yield Passive()

        while True:
            haltreq = yield dmi_monitor.cpu.running_state_interface.haltreq
            resumereq = yield dmi_monitor.cpu.running_state_interface.resumereq

            if haltreq:
                for _ in range(timeout_ticks):
                    ack = yield dmi_monitor.cpu.running_state_interface.haltack
                    if ack:
                        break
                    yield
                else:
                    raise ValueError(f"haltreq didnt get an ack in {timeout_ticks} ticks!")

            if resumereq:
                for _ in range(timeout_ticks):
                    ack = yield dmi_monitor.cpu.running_state_interface.resumeack
                    if ack:
                        break
                    yield
                else:
                    raise ValueError(f"resumereq didnt get an ack in {timeout_ticks} ticks!")
            yield
    return aux
