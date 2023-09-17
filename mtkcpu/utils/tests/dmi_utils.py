
from amaranth import Signal, Elaboratable
from amaranth.hdl import rec
from amaranth import Module, Cat, Signal
from amaranth.sim import Passive

from mtkcpu.units.debug.types import *
from mtkcpu.utils.misc import get_color_logging_object, get_members
from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.units.debug.types import DMI_reg_kinds
from mtkcpu.utils.tests.sim_tests import get_state_name
from mtkcpu.cpu.isa import Funct3
from mtkcpu.units.csr.csr_handlers import DCSR, DPC

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

        cpu_if = dmi_monitor.cpu.running_state_interface
        
        while True:
            
            related_signals = ["haltreq", "haltack", "resumereq", "resumeack"]

            for x in related_signals:
                val = yield getattr(cpu_if, x)
                locals()[x] = val
            
            if (yield cpu_if.error_sticky):
                lst = []
                for name in related_signals:
                    lst.append(f"{name}={locals()[name]}({locals()[f'prev_{name}']})")

                msg = ", ".join(lst)
                raise ValueError(f"CpuRunningStateExternalInterface misuse detected! {msg}")
            
            for x in related_signals:
                locals()[f"prev_{x}"] = val
                
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

def monitor_abstractauto(dmi_monitor: DMI_Monitor):
    from beepy import beep
    def aux():
        yield Passive()

        while True:
            new_dmi_transaction = yield dmi_monitor.new_dmi_transaction
            if new_dmi_transaction:
                op   = yield dmi_monitor.cur_dmi_bus.op
                addr = yield dmi_monitor.cur_dmi_bus.address
                if (op, addr) == (DMIOp.WRITE, DMIReg.ABSTRACTAUTO):
                        for _ in range(4):
                            logging.warn("")
                        struct = dmi_monitor.cpu.debug.dmi_regs[DMIReg.COMMAND]
                        reg_dump = debug_inspect_applied_struct(struct, (yield struct.as_value()))
                        logging.warn(f"COMMAND during ABSTRACTAUTO write: {reg_dump}")
                if (op, addr) == (DMIOp.WRITE, DMIReg.DMCONTROL):
                    cpu_dmactive = yield dmi_monitor.cpu.debug.dmi_regs[DMIReg.DMCONTROL].dmactive
                    value = yield dmi_monitor.cur_dmi_bus.data
                    write_dmactive = yield dmi_monitor.cur_DMCONTROL.dmactive
                    from multiprocessing import Process
                    # Process(target=beep, args=(6,)).start()
                    logging.info(f"<< >> CPU dmactive {cpu_dmactive}, write dmactive {write_dmactive} << >>")
                    if value & 0x2:
                        # ndmreset is 0x2.
                        Process(target=beep, args=(4,)).start()
                        for _ in range(4):
                            logging.info("<< >> << >>")

            yield
    return aux

def pprint_bin_chunked(val: int, bits_high_to_low: list[int]) -> str:
    res_fn = lambda lst: '_'.join(reversed(lst))
    res = []
    cur_offset = 0
    for x in reversed(bits_high_to_low):
        full_mask = (2 ** x) - 1  # only 1s in bit repr.
        masked_val = (val >> cur_offset) & full_mask
        res.append(
            format(masked_val, f'0{x}b')
        )
        cur_offset += x
    return res_fn(res)


class Color:
    yellow = "\x1b[33m"
    green = "\x1b[32m"
    red = "\x1b[21m"
    bold_red = "\x1b[31;1m"
    bold = "\033[1m"
    uline = "\033[4m"
    reset = "\x1b[0m"
    cyan = "\x1b[36m"
    blue = "\x1b[34m"

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
                        reg_dump = reg_dump.replace("resumereq=0x1", f"{Color.cyan}resumereq=0x1{Color.green}")
                        reg_dump = reg_dump.replace("haltreq=0x1", f"{Color.blue}haltreq=0x1{Color.green}")

                    msg = f"(mtime={(yield dmi_monitor.cpu.mtime)})DMI: {action}, address: {addr!r}"
                    if op == DMIOp.WRITE:
                        msg += f", value: {hex(value)} aka {_bin(value)}, dump {reg_dump}"
                    print_fn(msg)

                    if op == DMIOp.READ:
                        if struct is None:
                            print_fn(f"Skipping waiting for DMI READ to complete "
                                     f"as DMI REG {addr} is not implemented, so no dump can be created.")
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
                        logging.critical(f"SETTING DATA0 to {hex(last_data0)}")

                    if addr == DMIReg.COMMAND:
                        assert op == DMIOp.WRITE
                        acc_reg = dmi_monitor.cur_COMMAND.control
                        regno = yield acc_reg.regno
                        write = yield acc_reg.write
                        transfer = yield acc_reg.transfer
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
                        if haltreq and cpu_halted:
                            logging.critical(f"Possibly a bug in CPU or in debugger: Attempt to haltreq when cpu is already halted!")
                            # prev_state = None
                            # prev_jtag_tap_dmi_bus = 0
                            # while True:
                            #     fsm = dmi_monitor.cpu.debug.fsm
                            #     state = get_state_name(fsm, (yield fsm.state))
                            #     if state != prev_state:
                            #         mtime = yield dmi_monitor.cpu.mtime
                            #         logging.critical(f"mtime={mtime}, entry to state {state}")
                            #         prev_state = state
                            #     haltack =       yield dmi_monitor.cpu.running_state_interface.haltack
                            #     resumeack =     yield dmi_monitor.cpu.running_state_interface.resumeack
                            #     cmd_finished =  yield dmi_monitor.cpu.debug.controller.command_finished
                            #     cmd_err =       yield dmi_monitor.cpu.debug.controller.command_err
                            #     if haltack or cmd_err or cmd_finished or resumeack:
                            #         logging.critical(f"(mtime={(yield dmi_monitor.cpu.mtime)}) haltack {haltack}, resumeack {resumeack}, cmderr: {cmd_err}, cmd_finished: {cmd_finished}")
                            #     if cmd_finished:
                            #         raise ValueError("OK")
                                
                            #     jtag_tap_dmi_bus    = yield dmi_monitor.cpu.debug.jtag.regs[JtagIR.DMI].w.as_value()
                            #     update              = yield dmi_monitor.cpu.debug.jtag.regs[JtagIR.DMI].update
                            #     if update:
                            #         logging.critical(f"(mtime={(yield dmi_monitor.cpu.mtime)}) UPDATE!")
                            #     if jtag_tap_dmi_bus != prev_jtag_tap_dmi_bus:
                            #         dmi_bus_bit_mask = [7, 32, 2]  # 7 bit addr, 32 bit data, 2 bit op
                            #         logging.critical(f"(mtime={(yield dmi_monitor.cpu.mtime)}) BUS was {pprint_bin_chunked(prev_jtag_tap_dmi_bus, dmi_bus_bit_mask)}, now is {pprint_bin_chunked(jtag_tap_dmi_bus, dmi_bus_bit_mask)} (aka {hex(jtag_tap_dmi_bus)})")
                            #         prev_jtag_tap_dmi_bus = jtag_tap_dmi_bus

                            #     yield
                    
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
    
    # TODO
    # Bus zeroing should be stated explicitely, but i don't yet know good place for that..
    yield dmi_monitor.cur_dmi_bus.as_value().eq(0)


def dmi_op_wait_for_success(dmi_monitor: DMI_Monitor, timeout: int = 40):
    yield from dmi_op_wait_for_cmderr(
        dmi_monitor=dmi_monitor,
        expected_cmderr=ABSTRACTCS_Layout.CMDERR.NO_ERR,
        timeout=timeout
    )


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


def activate_DM(dmi_monitor: DMI_Monitor):
    yield from DMCONTROL_setup_basic_fields(dmi_monitor=dmi_monitor, dmi_op=DMIOp.WRITE)
    yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
    yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor, timeout=20)

def activate_DM_and_halt_via_dmi(dmi_monitor: DMI_Monitor):
    # Only assert 'dmactive'.
    yield from activate_DM(dmi_monitor=dmi_monitor)

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
            mtime = yield dmi_monitor.cpu.mtime
            if dmactive != prev_dmactive:
                repr = "active" if dmactive else "inactive"
                note = "from initial" if prev_dmactive is None else ""
                logging.info(f"(mtime={mtime}) DM changed state {note} to {repr}")
            prev_dmactive = dmactive
            
            cpu_state = yield dmi_monitor.cpu.running_state.halted
            if cpu_state != prev_cpu_state:
                repr = "halted" if cpu_state else "running"
                note = "from initial" if prev_cpu_state is None else ""
                logging.info(f"(mtime={mtime}) CPU changed state {note} to {repr}")
            prev_cpu_state = cpu_state

            yield
    return aux


def monitor_halt_or_resume_req_get_ack(dmi_monitor: DMI_Monitor, timeout_ticks: int = 20):
    def aux():
        yield Passive()

        while True:
            haltreq = yield dmi_monitor.cpu.running_state_interface.haltreq
            resumereq = yield dmi_monitor.cpu.running_state_interface.resumereq

            # NOTE: it is legal for debugger to set 'resumereq' when the hart is not halted (it just has no effect)
            # (analogically with 'haltreq'). Actually, openOCD does this at some point..

            # TODO: maybe it could be relaxed.
            assert not (haltreq and resumereq)

            if haltreq:
                halted = yield dmi_monitor.cpu.running_state.halted 
                if not halted:
                    for _ in range(timeout_ticks):
                        ack = yield dmi_monitor.cpu.running_state_interface.haltack
                        if ack:
                            break
                        yield
                    else:
                        raise ValueError(f"haltreq didnt get an ack in {timeout_ticks} ticks!")

            if resumereq:
                halted = yield dmi_monitor.cpu.running_state.halted 
                if halted:
                    for _ in range(timeout_ticks):
                        ack = yield dmi_monitor.cpu.running_state_interface.resumeack
                        if ack:
                            break
                        yield
                    else:
                        raise ValueError(f"resumereq didnt get an ack in {timeout_ticks} ticks!")
            yield
    return aux


def monitor_writes_to_gpr(dmi_monitor: DMI_Monitor, gpr_num: int):
    def aux():
        yield Passive()
        prev_x = 0
        assert gpr_num in range(1, 33)
        while True:
            x = yield dmi_monitor.cpu.regs._array._inner[gpr_num]
            if x != prev_x:
                logging.critical(f">>> {hex(x)} written to x{gpr_num}")
                prev_x = x
            yield
    return aux

def monitor_writes_to_dcsr(dmi_monitor: DMI_Monitor):

    dcsr_addr = DCSR.addr
    dpc_addr = DPC.addr
    
    def aux():
        yield Passive()
        csr_unit = dmi_monitor.cpu.csr_unit
        while True:
            csr_unit_active = yield csr_unit.en
            csr_idx         = yield csr_unit.csr_idx
            funct3          = yield csr_unit.func3
            rs1             = yield csr_unit.rs1
            rs1val          = yield csr_unit.rs1val
            if csr_unit_active:
                if funct3 in [Funct3.CSRRS, Funct3.CSRRSI]:
                    if rs1val == 0:
                        yield
                        continue # not interesting - only read.
                    if csr_idx == dcsr_addr:
                        logging.critical(f"------       DCSR write: {Funct3(funct3)}, rs1 {rs1}, rs1val {rs1val}")
                    elif csr_idx == dpc_addr:
                        logging.critical(f"------       DPC write: {Funct3(funct3)}, rs1 {rs1}, rs1val {rs1val}")
                if funct3 in [Funct3.CSRRW]:
                    if csr_idx == dcsr_addr:
                        logging.critical(f"------       DCSR write: {Funct3(funct3)}, rs1 {rs1}, rs1val {rs1val}")
                if funct3 in [Funct3.CSRRWI]:
                    raise NotImplementedError()
            yield
    return aux

def monitor_pc_and_main_fsm(dmi_monitor: DMI_Monitor, wait_for_first_haltreq: bool = True):
    from mtkcpu.utils.tests.sim_tests import get_state_name
    def aux():
        yield Passive()

        cpu = dmi_monitor.cpu
        
        if wait_for_first_haltreq:
            # To avoid spam, wait till first haltreq debugger event.
            while True:
                haltreq = yield cpu.running_state_interface.haltreq
                if haltreq:
                    break
                yield
        
        log_fn = lambda x: logging.critical(f"\t\t\t\t {x}")
        prev_state = None
        prev_pc = 0x0
        while True:
            state = get_state_name(cpu.main_fsm, (yield cpu.main_fsm.state))
            pc = hex((yield cpu.pc))
            if state == "FETCH" and state != prev_state:
                log_fn(f"detected state change: {prev_state} -> FETCH. pc changed from {prev_pc} to {pc}.")
                prev_pc = pc
            if state == "DECODE" and state != prev_state:
                log_fn(f"instr: {hex((yield cpu.instr))}")
            if state == "TRAP" and state != prev_state:
                instr = yield cpu.instr
                log_fn(f"TRAP at pc {pc} at state {prev_state}, instr {hex(instr)}")
            prev_state = state
            yield
    return aux


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
            addr = yield gb.addr
            ack = yield gb.ack
            if en and store and ack:
                data = yield gb.write_data
                msg = f"MEMORY BUS ACTIVE: addr={hex(addr)}, is_store={store}, data={hex(data)}"
                logging.critical(msg)
                output_dict[addr] = data
            yield
    return f
