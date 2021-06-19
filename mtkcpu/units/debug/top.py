from nmigen.hdl.rec import Layout
from nmigen import *
from enum import IntEnum

from mtkcpu.units.debug.jtag import JTAGTap, JtagIR, JtagIRValue, DMISTAT, debug_module_get_width

# * The Debug Module’s ownstate and registers should only be reset at power-up and while dmactiveindmcontrol is 0.


class DMIReg(IntEnum):
    DMSTATUS = 0x11
    DMCONTROL = 0x10
    HARTINFO = 0x12
    ABSTRACTS = 0x16
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
        ("clrresethaltreq", 1),
        ("setresethaltreq", 1),
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
}


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
    NOP    = 0
    READ    = 1
    WRITE   = 2

def dmcontrol_handler(record, dummy, m):
    sync = m.d.sync
    sync += dummy.eq(1)
    # with m.If(record.w.dmactive):
    #     sync += record.w.dmactive.eq(1)


handlers = {
    DMIReg.DMCONTROL: dmcontrol_handler,
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

        dtmcs   = self.jtag.regs[JtagIR.DTMCS]
        dmi     = self.jtag.regs[JtagIR.DMI]
        idcode  = self.jtag.regs[JtagIR.IDCODE]

        comb += [
            idcode.r.eq(JtagIRValue.IDCODE),

            dtmcs.r.version.eq(JtagIRValue.DM_VERSION),
            dtmcs.r.abits.eq(JtagIRValue.DM_ABITS),
            dtmcs.r.dmistat.eq(DMISTAT.NO_ERR),
            dtmcs.r.idle.eq(2), # TODO
        ]

        self.HANDLER = Signal()

        HANDLE_ME_PLZ = 0
        sticky = Signal(reset=HANDLE_ME_PLZ)

        with m.If(dtmcs.update & dtmcs.w.dmireset):
            comb += sticky.eq(0) # TODO

        dmi_op      = self.dmi_op       = Signal(DMIOP)# Signal(debug_module_get_width(JtagIR.DMI, "op"))
        dmi_address = self.dmi_address  = Signal(debug_module_get_width(JtagIR.DMI, "address"))
        dmi_data    = self.dmi_data     = Signal(debug_module_get_width(JtagIR.DMI, "data"))

        self.dmi_regs = dict([(k, Record(reg_make_rw(v))) for k, v in dmi_regs.items()])


        DBG_DMI_ADDR = self.DBG_DMI_ADDR = Signal(DMIReg)
        comb += DBG_DMI_ADDR.eq(dmi_address)

        sync += [
            dmi_op.eq(dmi.w.op),
            dmi_address.eq(dmi.w.address),
            dmi_data.eq(dmi.w.data),
        ]


        sync += [
            dmi.r.address.eq(dmi_address),
            # dmi.r.op.eq(0),
        ]


        self.ONREAD = Signal()
        self.ONWRITE = Signal()

        def on_read(addr):
            sync = self.m.d.sync
            with m.Switch(addr):
                for addr2, record in self.dmi_regs.items():
                    with m.Case(addr2):
                        sync += dmi.r.data.eq(record.w), # TODO record.w
                        sync += dmi.r.op.eq(0),
            sync += self.ONREAD.eq(1)
            

        def on_write(addr, data):
            sync = self.m.d.sync
            sync += self.ONWRITE.eq(1)
            with m.Switch(addr):
                for addr2, record in self.dmi_regs.items():
                    with m.Case(addr2):
                        # sync += dmi.r.eq(record.r)
                        sync += record.w.eq(data)


        sync += [
            self.ONWRITE.eq(0),
            self.ONREAD.eq(0),
            self.HANDLER.eq(0),
        ]

        # DTM starts the operation specified in op unless the current status reported in op is sticky.
        with m.If(dmi.update & ~sticky):
            with m.Switch(dmi_op):
                with m.Case(DMIOp.NOP):
                    pass
                with m.Case(DMIOp.READ):
                    on_read(dmi_address)
                with m.Case(DMIOp.WRITE):
                    on_write(dmi_address, dmi_data)


        with m.Switch(dmi_address):
            for reg, handler in handlers.items():
                with m.Case(reg):
                    handler(self.dmi_regs[reg], self.HANDLER, m)


        #  duplicate  
        sync += [
            # TODO i use 'w' because below its sync += r.data.eq(record.w)
            self.dmi_regs[DMIReg.DMSTATUS].w.version.eq(2),
            self.dmi_regs[DMIReg.DMSTATUS].w.authenticated.eq(1),

            self.dmi_regs[DMIReg.DMCONTROL].r.hartsello.eq(1),
            self.dmi_regs[DMIReg.DMCONTROL].r.hartselhi.eq(0),
        ]

        return m
