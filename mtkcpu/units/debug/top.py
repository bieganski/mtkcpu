from typing import overload
from nmigen.hdl.rec import Layout
from nmigen import *
from enum import IntEnum

from mtkcpu.units.debug.jtag import JTAGTap, JtagIR, JtagIRValue, DMISTAT, debug_module_get_width

# * The Debug Module’s own state and registers should only 
# be reset at power-up and while dmactive in dmcontrol is 0.


class DMIReg(IntEnum):
    DMSTATUS = 0x11
    DMCONTROL = 0x10
    HARTINFO = 0x12
    ABSTRACTS = 0x16
    COMMAND = 0x17
    SBCS = 0x38


dmi_regs = {
    DMIReg.DMSTATUS: [
        ("version",           4),
        ("confstrptrvalid",   1),
        ("hasresethaltreq",   1),
        ("authbusy",          1),
        ("authenticated",     1),
        ("anyhalted",         1),
        ("allhalted",         1),
        ("anyrunning",        1),
        ("allrunning",        1), # 1_or_0 if in debug mode
        ("anyunavail",        1),
        ("allunavail",        1),
        ("anynonexistent",    1),
        ("allnonexistent",    1),
        ("anyresumeack",      1),
        ("allresumeack",      1),
        ("anyhavereset",      1),
        ("allhavereset",      1),
        ("_zero0",            2),
        ("impebreak",         1), # R, 1 if implicit ebreak at the end of program buffer
        ("_zero1",            9),
    ],
    DMIReg.DMCONTROL: [
        ("dmactive", 1),
        ("ndmreset", 1),
        ("clrresethaltreXq", 1),
        ("setresethaltreXq", 1),
        ("_zero1",  2),
        ("hartselhi", 10),
        ("hartsello", 10),
        ("hasel",    1),
        ("_zero2",   1),
        ("ackhavereset",   1),
        ("hartreset",1),
        ("resumereq",1),
        ("haltreq",  1),
    ],
    DMIReg.HARTINFO: [
        ("dataaddr", 12),
        ("datasize", 4),
        ("dataaccess", 1),
        ("_zero1", 3),
        ("nscratch", 4),
        ("_zero2", 8),
    ],

    DMIReg.ABSTRACTS: [
        ("datacount", 4),
        ("_zero1", 4),
        ("cmderr", 3),
        ("_zero2", 1),
        ("busy", 1),
        ("_zero3", 11),
        ("progbufsize", 5),
        ("_zero4", 3),
    ],

    DMIReg.COMMAND: [
        ("control", 24),
        ("cmdtype", 8)
    ],
}

class DMICommand(IntEnum):
    AccessRegister = 0x0

command_regs = {
    DMICommand.AccessRegister: [
        ("regno", 16),
        ("write", 1),
        ("transfer", 1),
        ("postexec", 1),
        ("_zero1", 1),
        ("size", 3),
        ("_zero2", 1),
    ]
}

reg_len = lambda lst: sum(map(lambda x : x[1], lst))
assert all(map(lambda lst: 32 == reg_len(lst), dmi_regs.values()))
assert all(map(lambda lst: 24 == reg_len(lst), command_regs.values()))


def reg_make_rw(layout):
    from nmigen.hdl.rec import DIR_FANIN, DIR_FANOUT, Record, Layout
    # assert all(len(x) == 2 for x in layout) or all(len(x) == 3 for x in layout)

    def f(x):
        if len(x) == 2:
            return tuple([*x, DIR_FANOUT])
        else:
            return x
    
    res = [
        ("r", list(map(f, layout))),
        ("w", list(map(f, layout))),
        ("update", 1, DIR_FANOUT),
    ]

    return Layout(res)

class DMIOp(IntEnum):
    NOP     = 0
    READ    = 1
    WRITE   = 2

class ControllerInterface():
    def __init__(self):
        self.halted             = Signal()
        self.resumed            = Signal()
        self.command_err        = Signal()
        self.command_finished   = Signal()


class HandlerDMI():
    def __init__(self, debug_unit, dmi_regs, controller) -> None:
        # self.m = m
        self.debug_unit = debug_unit
        self.dmi_regs = dmi_regs
        self.controller = controller

        m = self.debug_unit.m
        self.reg_dmcontrol  = self.dmi_regs[DMIReg.DMCONTROL]
        self.reg_dmstatus   = self.dmi_regs[DMIReg.DMSTATUS]
        self.reg_command    = self.dmi_regs[DMIReg.COMMAND]
        self.sync = m.d.sync
        self.comb = m.d.comb

    def handle_write(self):
        raise NotImplementedError("DMI Handler must implement 'handle_write(self)' method!")

class HandlerDMCONTROL(HandlerDMI):

    # def decorate(f):
    #     def g(*args, **kwargs):
    #         slf = args[0]
    #         kwargs["sync"] = slf.debug_unit.m.d.sync
    #         return f(*args, **kwargs)
    #     return g

    # @decorate
    def handle_write(self):
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb

        with m.If(self.reg_dmcontrol.w.dmactive):
            # sync += self.debug_unit.WTF.eq(1)
            sync += self.reg_dmcontrol.r.dmactive.eq(1)

            # comb += self

            with m.If(self.reg_dmcontrol.w.haltreq):
                # sync += self.debug_unit.WTF.eq(2)
                sync += self.debug_unit.HALT.eq(1)
                sync += self.reg_dmstatus.r.allhalted.eq(1)


class HandlerCOMMAND(HandlerDMI):
    def handle_write(self):
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb

        sync += self.debug_unit.WTF.eq(3)

        with m.FSM() as fsm:
            with m.State("LOAD"):
                with m.Switch(self.reg_command.w.cmdtype):
                    for k, v in self.debug_unit.command_regs.items():
                        with m.Case(k):
                            sync += self.debug_unit.command_regs[k].eq(self.reg_command.w.control)
                m.next = "RUN"
            with m.State("RUN"):
                sync += self.controller.command_finished.eq(1)
                m.next = "LOAD"


handlers = {
    DMIReg.DMCONTROL: HandlerDMCONTROL,
    DMIReg.COMMAND: HandlerCOMMAND,
}

class DMIOP(IntEnum):
    NOP = 0
    READ = 1
    WRITE = 2

# Jtag FSM described here:
# https://www.xilinx.com/support/answers/3203.html
class DebugUnit(Elaboratable):
    def __init__(self):
        pass

    def elaborate(self, platform):
        m = self.m = Module()
        sync = m.d.sync
        comb = m.d.comb

        self.jtag = m.submodules.jtag = JTAGTap()

        jtag_dtmcs   = self.jtag.regs[JtagIR.DTMCS]
        jtag_dmi     = self.jtag.regs[JtagIR.DMI]
        jtag_idcode  = self.jtag.regs[JtagIR.IDCODE]

        comb += [
            jtag_idcode.r.eq(JtagIRValue.IDCODE),

            jtag_dtmcs.r.version.eq(JtagIRValue.DM_VERSION),
            jtag_dtmcs.r.abits.eq(JtagIRValue.DM_ABITS),
            jtag_dtmcs.r.dmistat.eq(DMISTAT.NO_ERR),
            jtag_dtmcs.r.idle.eq(2), # TODO
        ]

        self.HALT = Signal()

        self.HANDLER = Signal()

        HANDLE_ME_PLZ = 0
        sticky = Signal(reset=HANDLE_ME_PLZ)

        with m.If(jtag_dtmcs.update & jtag_dtmcs.w.dmireset):
            comb += sticky.eq(0) # TODO

        dmi_op      = self.dmi_op       = Signal(DMIOP)# Signal(debug_module_get_width(JtagIR.DMI, "op"))
        dmi_address = self.dmi_address  = Signal(debug_module_get_width(JtagIR.DMI, "address"))
        dmi_data    = self.dmi_data     = Signal(debug_module_get_width(JtagIR.DMI, "data"))

        self.dmi_regs = dict([(k, Record(reg_make_rw(v))) for k, v in dmi_regs.items()])

        self.command_regs = dict([(k, Record(v)) for k, v in command_regs.items()])

        self.controller = ControllerInterface()

        self.dmi_handlers = dict(
            [ 
                ( k, v(self, self.dmi_regs, self.controller) ) for k, v in handlers.items()
            ]
        )

        DBG_DMI_ADDR = self.DBG_DMI_ADDR = Signal(DMIReg)
        comb += DBG_DMI_ADDR.eq(dmi_address)

        sync += [
            dmi_op.eq(jtag_dmi.w.op),
            dmi_address.eq(jtag_dmi.w.address),
            dmi_data.eq(jtag_dmi.w.data),
        ]


        sync += [
            jtag_dmi.r.address.eq(dmi_address),
            # dmi.r.op.eq(0),
        ]

        

        self.ONREAD = Signal()
        self.ONWRITE = Signal()

        self.WTF = Signal(2)
        sync += self.WTF.eq(0)

        sync += [
            self.ONWRITE.eq(0),
            self.ONREAD.eq(0),
            self.HANDLER.eq(0),
        ]

        def on_read(addr):
            sync = self.m.d.sync
            sync += self.ONREAD.eq(1)
            with m.Switch(addr):
                for addr2, record in self.dmi_regs.items():
                    with m.Case(addr2):
                        sync += jtag_dmi.r.data.eq(record.r),
                        sync += jtag_dmi.r.op.eq(0), # TODO        

        def on_write(addr, data):
            sync = self.m.d.sync
            sync += self.ONWRITE.eq(1)
            with m.Switch(addr):
                for addr2, record in self.dmi_regs.items():
                    with m.Case(addr2):
                        sync += record.w.eq(data)

        updated = Signal()

        sync += [
            updated.eq(jtag_dmi.update),
        ]

        # DTM starts the operation specified in op unless the current status reported in op is sticky.
        with m.If(jtag_dmi.update & ~sticky):
            with m.Switch(dmi_op):
                with m.Case(DMIOp.NOP):
                    pass
                with m.Case(DMIOp.READ):
                    on_read(dmi_address)
                with m.Case(DMIOp.WRITE):
                    on_write(dmi_address, dmi_data)
                    # with m.If(dmi_address == DMIReg.COMMAND):
                    #     sync += self.WTF.eq(2)
                    
        # Separate 'updated' signal, as we must wait for record to be filled.
        with m.If(updated):
            with m.Switch(dmi_address):
                for reg, h in self.dmi_handlers.items():
                    with m.Case(reg):
                        h.handle_write()
            # with m.If(dmi_address == DMIReg.COMMAND):
                

        sync += [
            self.dmi_regs[DMIReg.DMSTATUS].r.version.eq(2),
            self.dmi_regs[DMIReg.DMSTATUS].r.authenticated.eq(1),

            self.dmi_regs[DMIReg.DMCONTROL].r.hartsello.eq(1),
            self.dmi_regs[DMIReg.DMCONTROL].r.hartselhi.eq(0),
        ]

        return m
