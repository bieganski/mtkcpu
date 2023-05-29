from typing import overload, Dict
from amaranth import *
from enum import IntEnum

from mtkcpu.units.debug.jtag import JTAGTap
from mtkcpu.units.debug.types import DMIOp, DMICommand, DMIReg, DMI_COMMAND_reg_kinds, DMI_reg_kinds, IR_DMI_Layout, JtagIR, JtagIRValue, DMISTAT

from amaranth.lib import data
from typing import Type

# * The Debug Module’s own state and registers should only 
# be reset at power-up and while dmactive in dmcontrol is 0.


# TODO
# * add 'mark_command_finished' handler's method
# * 'dmi_address' cannot be set independently of main FSM state - eve if in WAIT state


#  If an  exception  is  encountered  during  execution  of  the  Program  Buffer, 
#  no  more  instructions  are executed,  the  hart  remains  in  Debug  Mode,  
#  and cmderr is  set  to  3  (exception error).



PROGBUFSIZE = 3
DATASIZE = 2
PROGBUF_MMIO_ADDR = 0xde88


# https://people.eecs.berkeley.edu/~krste/papers/riscv-privileged-v1.9.1.pdf    
class DMI_CSR(IntEnum):
    MISA = 0x301
    DCSR = 0x7B0 # TODO from debug spec: pc saved in dpc and cause is updated
    DPC  = 0x7B1

class DebugCSR():
    # constructor needs CPU instance to use/drive CPU signals
    def __init__(self, layout, cpu):
        self.layout = layout
        self.cpu = cpu

    @overload
    def field_values(self) -> Dict[str, Signal]:
        raise NotImplementedError("DebugCSR must implement 'field_values(self)' method!")


# coupled in comb. logic
class ReadOnlyRegValue():

    def __init__(self, layout) -> None:
        self.layout = layout

    @overload
    def field_values(self) -> Dict[str, int]:
        raise NotImplementedError("ReadOnlyRegValue must implement 'field_values(self)' method!")

    # converts values of all fields to single number 
    def to_value(self):
        field_vals = self.field_values()
        res, off = 0, 0
        for name, width in reversed(self.layout):
            if "_zero" in name:
                continue
            res |= field_vals[name] << off
            off += width
        return res

# https://people.eecs.berkeley.edu/~krste/papers/riscv-privileged-v1.9.pdf
class RegValueMISA(ReadOnlyRegValue):
    class XLEN(IntEnum):
        RV32 = 0x1
    class Extension(IntEnum):
        I = 1 << 8

    def field_values(self) -> Dict[str, int]:
        return {
            "base": self.XLEN.RV32,
            "extensions": self.Extension.I,
            "wiri": 0,
        }

class RegValueDPC(DebugCSR):
    def field_values(self) -> Dict[str, Signal]:
        return {

        }


dbg_csr_regs = {
    DMI_CSR.MISA: [
        ("extensions", 26),
        ("wiri", 4),
        ("base", 2),
    ],
    DMI_CSR.DPC: [
        ("value", 32),
    ]
}

const_csr_values = {
    DMI_CSR.MISA: RegValueMISA,
}


def reg_make_rw(type: Type[data.View]) -> data.View:
    """
    TODO: unify with 'jtagify_dr' from jtag.py.
    """

    layout = data.StructLayout({
        "r": data.Layout.cast(type),
        "w": data.Layout.cast(type),
    })

    return data.Signal(layout)

class ControllerInterface():
    def __init__(self):
        self.halted             = Signal()
        self.resumed            = Signal()
        self.command_err        = Signal(3) # of shape 'cmderr'
        self.command_finished   = Signal()


# Each handler notifies top level that he finished by setting
# controller.command_finished = 1 (in comb domain).
# In same clock cycle it can drive any sync signal, it will be executed too (e.g. FSM state transition).
class HandlerDMI():
    def __init__(self, my_reg_addr, debug_unit, dmi_regs, controller) -> None:
        self.debug_unit = debug_unit
        self.dmi_regs = dmi_regs
        self.controller = controller
        self.my_reg_addr = my_reg_addr


        # TODO replace me with reg = self.dmi_regs[my_reg_addr]
        # TODO or maybe not, as problem for DATA0-DATA15 etc.
        self.reg_dmcontrol  = self.dmi_regs[DMIReg.DMCONTROL]
        self.reg_dmstatus   = self.dmi_regs[DMIReg.DMSTATUS]
        self.reg_command    = self.dmi_regs[DMIReg.COMMAND]
        self.reg_abstractauto = self.dmi_regs[DMIReg.ABSTRACTAUTO]
    
        m = self.debug_unit.m
        self.sync = m.d.sync
        self.comb = m.d.comb

    def handle_write(self):
        raise NotImplementedError("DMI Handler must implement 'handle_write(self)' method!")

class HandlerDATA(HandlerDMI):
    def handle_write(self):
        num = self.my_reg_addr - DMIReg.DATA0
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb

        with m.If(self.debug_unit.autoexecdata & (1 << num)):
            # trigger COMMAND handler manually and let it mark command handle finished.
            self.debug_unit.dmi_handlers[DMIReg.COMMAND].handle_write()
            # with m.FSM():
            #     with m.State("A"):
            #         # normally 'on_write' function would do that
            #         sync += self.dmi_regs[DMIReg.COMMAND].w.eq(self.debug_unit.dmi_data)
            #         m.next = "B"
            #     with m.State("B"):
            #         self.debug_unit.dmi_handlers[DMIReg.COMMAND].handle_write()
            #         with m.If(self.controller.command_finished):
            #             m.next = "A"
        with m.Else():
            # do nothing
            comb += self.controller.command_finished.eq(1)
        

class HandlerABSTRACTAUTO(HandlerDMI):
    def handle_write(self):
        m = self.debug_unit.m
        # TODO maszyna stanów niepotrzebna
        with m.FSM():
            with m.State("A"):
                self.sync += self.debug_unit.autoexecdata.eq(self.reg_abstractauto.w.autoexecdata)
                m.next = "B"
            with m.State("B"):
                m.next = "A"
                self.comb += self.controller.command_finished.eq(1)


class HandlerDMCONTROL(HandlerDMI):

    def handle_write(self):
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb

        write_value = self.reg_dmcontrol.w

        with m.If(write_value.dmactive):
            sync += self.reg_dmcontrol.r.dmactive.eq(1)

            with m.If(write_value.haltreq):
                sync += self.debug_unit.HALT.eq(1)
                sync += self.reg_dmstatus.r.allhalted.eq(1)
                sync += self.reg_dmstatus.r.anyhalted.eq(1)
            
            with m.If(write_value.resumereq):
                # with m.If(write_value.step): # TODO step does not exist yet.
                #     pass # TODO auto-halt after single instruction
                sync += self.debug_unit.HALT.eq(0)
                sync += self.reg_dmstatus.r.allresumeack.eq(1)
                sync += self.reg_dmstatus.r.anyresumeack.eq(1)
                sync += self.reg_dmstatus.r.allhalted.eq(0)
                sync += self.reg_dmstatus.r.anyhalted.eq(0)
            
            # Only hart 0 exists.
            sync += self.reg_dmstatus.r.anynonexistent.eq(Cat(write_value.hartselhi, write_value.hartsello).bool())
        with m.Else():
            pass # TODO - reset the DM!
        
        comb += self.controller.command_finished.eq(1)


class HandlerCOMMAND(HandlerDMI):
    def handle_write(self):
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb

        with m.Switch(self.reg_command.w.cmdtype):
            for k, v in self.debug_unit.command_regs.items():
                with m.Case(k):
                    comb += self.debug_unit.command_regs[k].eq(self.reg_command.w.control)

        with m.If(self.reg_command.w.cmdtype == DMICommand.AccessRegister):
            # TODO
            # we use Record here to have named fields.
            record = self.debug_unit.command_regs[DMICommand.AccessRegister]
            with m.If(record.aarsize > 2):
                # with m.If(record.postexec | (record.aarsize != 2) | record.aarpostincrement):
                comb += self.controller.command_err.eq(2)
                comb += self.controller.command_finished.eq(1)
            with m.Else():
                with m.If(record.transfer):
                    dst = self.debug_unit.dmi_regs[DMIReg.DATA0].r # XXX rename
                    # decode register address, as it might be either CSR or GPR
                    with m.If(record.regno <= 0x0fff):
                        with m.If(record.write):
                            self.controller.command_finished.eq(1)
                            self.controller.command_err.eq(2)
                        # CSR
                        with m.Switch(record.regno):
                            for addr, _ in self.debug_unit.csr_regs.items():
                                with m.Case(addr):
                                    if addr in self.debug_unit.const_csr_values:
                                        with m.If(record.write):
                                            self.controller.command_finished.eq(1)
                                            self.controller.command_err.eq(2)
                                        with m.Else():
                                            cls = self.debug_unit.const_csr_values[addr]
                                            layout = self.debug_unit.csr_regs[addr]
                                            sync += dst.eq(cls(layout).to_value())
                                    else:
                                        with m.If(record.write):
                                            dst2 = self.debug_unit.dmi_regs[DMIReg.DATA0].w # XXX rename
                                            self.debug_unit.nonconst_csr_values[addr].eq(dst2)
                                        with m.Else():
                                            sync += dst.eq(self.debug_unit.nonconst_csr_values[addr])                                    
                                    
                            with m.Case(DMI_CSR.DPC):
                                sync += dst.eq(self.debug_unit.cpu.pc)
                        comb += self.controller.command_finished.eq(1)
                    with m.Elif(record.regno <= 0x101f):
                        # GPR
                        with m.FSM():
                            with m.State("A"):
                                comb += self.debug_unit.cpu.gprf_debug_addr.eq(record.regno - 0x1000),
                                comb += self.debug_unit.cpu.gprf_debug_write_en.eq(record.write)
                                comb += self.debug_unit.cpu.gprf_debug_data.eq(self.debug_unit.dmi_regs[DMIReg.DATA0].w)
                                m.next = "B"
                            with m.State("B"):
                                with m.If(~record.write):
                                    sync += self.debug_unit.dmi_regs[DMIReg.DATA0].r.eq(self.debug_unit.cpu.gprf_debug_data)
                                m.next = "C"
                            with m.State("C"):
                                with m.If(~record.postexec):
                                    comb += self.controller.command_finished.eq(1)
                                    m.next = "A"
                                with m.Else():
                                    # execute Program Buffer
                                    # sync += self.debug_unit.cpu.pc.eq(PROGBUF_MMIO_ADDR)
                                    pass

class HandlerPROGBUF(HandlerDMI):
    def handle_write(self):
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb

        my_idx = self.my_reg_addr - DMIReg.PROGBUF0
        my_mmio_addr = PROGBUF_MMIO_ADDR + 4 * my_idx

        value = self.dmi_regs[self.my_reg_addr].w

        bus = self.debug_unit.cpu.debug_bus

        comb += [
            bus.en.eq(1),
            bus.store.eq(1),
            bus.write_data.eq(value),
            bus.addr.eq(my_mmio_addr),
            bus.mask.eq(0b1111),
        ]

        with m.If(bus.ack):
            self.comb += self.controller.command_finished.eq(1)


class HandlerABSTRACTCS(HandlerDMI):
    def handle_write(self):
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb

        # TODO
        # does openocd even tries to write it?


handlers = {
    DMIReg.DMCONTROL: HandlerDMCONTROL,
    DMIReg.COMMAND: HandlerCOMMAND,
    DMIReg.PROGBUF0: HandlerPROGBUF,
    DMIReg.PROGBUF1: HandlerPROGBUF,
    DMIReg.PROGBUF2: HandlerPROGBUF,
    DMIReg.DATA0: HandlerDATA,
    DMIReg.DATA1: HandlerDATA,
    DMIReg.ABSTRACTAUTO: HandlerABSTRACTAUTO,
}

# Jtag FSM described here:
# https://www.xilinx.com/support/answers/3203.html
class DebugUnit(Elaboratable):
    def __init__(self, cpu):
        self.cpu = cpu
        self.jtag = JTAGTap()
        self.HALT = Signal()

    def elaborate(self, platform):
        m = self.m = Module()
        sync = m.d.sync
        comb = m.d.comb

        m.submodules.jtag = self.jtag

        jtag_dtmcs   = self.jtag.regs[JtagIR.DTMCS]
        jtag_dmi     = self.jtag.regs[JtagIR.DMI]
        jtag_idcode  = self.jtag.regs[JtagIR.IDCODE]

        # raise ValueError(jtag_idcode.r)

        comb += [
            jtag_idcode.r.eq(JtagIRValue.IDCODE),

            jtag_dtmcs.r.version.eq(JtagIRValue.DM_VERSION),
            jtag_dtmcs.r.abits.eq(JtagIRValue.DM_ABITS),
            jtag_dtmcs.r.dmistat.eq(DMISTAT.NO_ERR),
            jtag_dtmcs.r.idle.eq(2), # TODO
        ]

        self.HANDLER = Signal()

        self.autoexecdata = Signal(DATASIZE)

        HANDLE_ME_PLZ = 0
        sticky = Signal(reset=HANDLE_ME_PLZ)

        with m.If(jtag_dtmcs.update & jtag_dtmcs.w.dmireset):
            comb += sticky.eq(0) # TODO

        def shape(layout_cls: data.StructLayout, field: str) -> Shape:
            return data.Layout.cast(layout_cls).members[field]

        dmi_op      = self.dmi_op       = Signal(shape(IR_DMI_Layout, "op"))
        dmi_address = self.dmi_address  = Signal(shape(IR_DMI_Layout, "address"))
        dmi_data    = self.dmi_data     = Signal(shape(IR_DMI_Layout, "data"))

        self.dmi_regs = dict([(k, reg_make_rw(v)) for k, v in DMI_reg_kinds.items()])
        # command registers are write only, no need to 'reg_make_rw', nor Record instances.
        self.command_regs = dict([(k, data.Signal(v)) for k, v in DMI_COMMAND_reg_kinds.items()])
        self.csr_regs = dbg_csr_regs
        self.const_csr_values = const_csr_values
        self.nonconst_csr_values = dict([(k,Record(v)) for k, v in self.csr_regs.items() if k not in self.const_csr_values])

        self.controller = ControllerInterface()

        self.dmi_handlers = dict(
            [ 
                ( k, v(k, self, self.dmi_regs, self.controller) ) for k, v in handlers.items()
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

        def reset():
            self.m.d.sync += [
                self.dmi_regs[DMIReg.DMSTATUS].r.version.eq(2),
                self.dmi_regs[DMIReg.DMSTATUS].r.authenticated.eq(1),

                self.dmi_regs[DMIReg.DMCONTROL].r.hartsello.eq(1),
                self.dmi_regs[DMIReg.DMCONTROL].r.hartselhi.eq(0),

                self.dmi_regs[DMIReg.ABSTRACTCS].r.datacount.eq(1),
                self.dmi_regs[DMIReg.ABSTRACTCS].r.progbufsize.eq(PROGBUFSIZE),
            ]

            self.m.d.comb += [
                self.controller.command_err.eq(0),
                self.controller.command_finished.eq(0),
            ]

        reset()

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

        with m.FSM() as fsm:
            with m.State("IDLE"):
                with m.If(jtag_dmi.update & ~sticky):
                    m.next = "IDLE"
                    with m.Switch(dmi_op):
                        with m.Case(DMIOp.NOP):
                            pass
                        with m.Case(DMIOp.READ):
                            on_read(dmi_address)            # moves data from command regs to jtag regs.
                        with m.Case(DMIOp.WRITE):
                            on_write(dmi_address, dmi_data) # takes data from jtag regs into command regs.
                            m.next = "WAIT"
                    # sync += self.dmi_regs[DMIReg.ABSTRACTS].r.busy.eq(1) # TODO
            with m.State("WAIT"):
                sync += self.dmi_regs[DMIReg.ABSTRACTCS].r.cmderr.eq(self.controller.command_err)
                with m.Switch(dmi_address):
                    for reg, h in self.dmi_handlers.items():
                        with m.Case(reg):
                            h.handle_write()
                with m.If(self.controller.command_finished):
                    m.next = "IDLE"
                    sync += self.dmi_regs[DMIReg.ABSTRACTCS].r.busy.eq(0) # TODO make busy=1 at some point

        return m
