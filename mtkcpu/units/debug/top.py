from typing import overload, Dict
from amaranth import *
from enum import IntEnum

from mtkcpu.units.debug.jtag import JTAGTap
from mtkcpu.units.debug.types import *

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
    def __init__(self, 
                 my_reg_addr: int, # TODO rename so that it contains 'dmi_addr'.
                 debug_unit: "DebugUnit",
                 dmi_regs: dict,
                 controller: ControllerInterface,
                 write_value: Signal,
            ):
        self.debug_unit = debug_unit
        self.dmi_regs = dmi_regs
        self.controller = controller
        self.my_reg_addr = my_reg_addr

        self.reg_dmcontrol      = self.dmi_regs[DMIReg.DMCONTROL]
        self.reg_dmstatus       = self.dmi_regs[DMIReg.DMSTATUS]
        self.reg_command        = self.dmi_regs[DMIReg.COMMAND]
        self.reg_abstractauto   = self.dmi_regs[DMIReg.ABSTRACTAUTO]
        self.reg_data0          = self.dmi_regs[DMIReg.DATA0]

        assert write_value.shape() == unsigned(32)
        self.write_value = write_value
    
        m = self.debug_unit.m
        self.sync = m.d.sync
        self.comb = m.d.comb

    def handle_write(self):
        raise NotImplementedError("DMI Handler must implement 'handle_write(self)' method!")
    
    def default_handle_write(self):
        """
        XXX rename to "handle_write" when ready to do so.
        """
        my_reg = self.debug_unit.dmi_regs[self.my_reg_addr]
        self.sync += [
            my_reg.eq(self.write_value),
        ]
        self.comb += [
            self.controller.command_finished.eq(1),
        ]

class HandlerDATA(HandlerDMI):
    def handle_write(self):
        num = self.my_reg_addr - DMIReg.DATA0
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb

        write_value = Signal(32) # XXX

        with m.If(self.debug_unit.autoexecdata & (1 << num)):
            # trigger COMMAND handler manually and let it mark command handle finished.
            self.debug_unit.dmi_handlers[DMIReg.COMMAND].handle_write()
        with m.Else():
            self.default_handle_write()

class HandlerABSTRACTAUTO(HandlerDMI):
    def handle_write(self):
        return # TODO
        m = self.debug_unit.m
        write_value : ABSTRACTAUTO_Layout = data.View(ABSTRACTAUTO_Layout, Signal(32)) # XXX

        # TODO FSM here is probably an overkill?
        with m.FSM():
            with m.State("A"):
                self.sync += self.debug_unit.autoexecdata.eq(write_value.autoexecdata)
                m.next = "B"
            with m.State("B"):
                m.next = "A"
                self.comb += self.controller.command_finished.eq(1)


class HandlerDMCONTROL(HandlerDMI):

    def handle_write(self):
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb

        write_value : DMCONTROL_Layout = data.View(DMCONTROL_Layout, Signal(32)) # XXX


        # Everything needed latched in a single cycle.
        comb += self.controller.command_finished.eq(1)

        with m.If(write_value.dmactive):
            sync += self.reg_dmcontrol.dmactive.eq(1)

            with m.If(write_value.haltreq):
                sync += self.debug_unit.HALT.eq(1)
                sync += self.reg_dmstatus.allhalted.eq(1)
                sync += self.reg_dmstatus.anyhalted.eq(1)
            
            with m.If(write_value.resumereq):
                # with m.If(write_value.step): # TODO step does not exist yet.
                #     pass # TODO auto-halt after single instruction
                sync += self.debug_unit.HALT.eq(0)
                sync += self.reg_dmstatus.allresumeack.eq(1)
                sync += self.reg_dmstatus.anyresumeack.eq(1)
                sync += self.reg_dmstatus.allhalted.eq(0)
                sync += self.reg_dmstatus.anyhalted.eq(0)
            
            # Only hart 0 exists.
            sync += self.reg_dmstatus.anynonexistent.eq(Cat(write_value.hartselhi, write_value.hartsello).bool())
        with m.Else():
            pass # TODO - reset the DM!
        

class HandlerCOMMAND(HandlerDMI):
    def handle_write(self):
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb
        
        write_value : COMMAND_Layout = data.View(COMMAND_Layout, self.write_value)

        access_register = COMMAND_Layout.AbstractCommandCmdtype.AccessRegister

        with m.If(write_value.cmdtype == access_register):

            acc_reg : AbstractCommandControl.AccessRegisterLayout = write_value.control.ar

            with m.If(acc_reg.aarsize != AbstractCommandControl.AccessRegisterLayout.AARSIZE.BIT32):
                # with m.If(record.postexec | (record.aarsize != 2) | record.aarpostincrement):
                comb += self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)
                comb += self.controller.command_finished.eq(1)
            with m.Else():
                with m.If(acc_reg.transfer):
                    dst = self.debug_unit.dmi_regs[DMIReg.DATA0] # XXX rename
                    # decode register address, as it might be either CSR or GPR
                    with m.If(acc_reg.regno <= 0x0fff):
                        # CSR
                        with m.If(acc_reg.write):
                            self.controller.command_finished.eq(1)
                            self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)
                        with m.Switch(acc_reg.regno):
                            for addr, _ in self.debug_unit.csr_regs.items():
                                with m.Case(addr):
                                    if addr in self.debug_unit.const_csr_values:
                                        with m.If(acc_reg.write):
                                            self.controller.command_finished.eq(1)
                                            self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)
                                        with m.Else():
                                            cls = self.debug_unit.const_csr_values[addr]
                                            layout = self.debug_unit.csr_regs[addr]
                                            sync += dst.eq(cls(layout).to_value())
                                    else:
                                        with m.If(acc_reg.write):
                                            self.debug_unit.nonconst_csr_values[addr].eq(write_value)
                                        with m.Else():
                                            sync += dst.eq(self.debug_unit.nonconst_csr_values[addr])                                    
                                    
                            with m.Case(DMI_CSR.DPC):
                                sync += dst.eq(self.debug_unit.cpu.pc)
                        comb += self.controller.command_finished.eq(1)
                    with m.Elif(acc_reg.regno <= 0x101f):
                        # GPR
                        with m.FSM():
                            with m.State("A"):
                                comb += self.debug_unit.cpu.gprf_debug_addr.eq(acc_reg.regno & 0xFF),
                                comb += self.debug_unit.cpu.gprf_debug_write_en.eq(acc_reg.write)
                                comb += self.debug_unit.cpu.gprf_debug_data.eq(write_value)
                                m.next = "B"
                            with m.State("B"):
                                with m.If(~acc_reg.write):
                                    sync += self.reg_data0.eq(self.debug_unit.cpu.gprf_debug_data)
                                m.next = "C"
                            with m.State("C"):
                                with m.If(~acc_reg.postexec):
                                    comb += self.controller.command_finished.eq(1)
                                    m.next = "A"
                                with m.Else():
                                    # execute Program Buffer
                                    # sync += self.debug_unit.cpu.pc.eq(PROGBUF_MMIO_ADDR)
                                    pass
                    with m.Else():
                        self.controller.command_finished.eq(1)
                        self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)


class HandlerPROGBUF(HandlerDMI):
    def handle_write(self):
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb

        my_idx = self.my_reg_addr - DMIReg.PROGBUF0
        my_mmio_addr = PROGBUF_MMIO_ADDR + 4 * my_idx

        write_value = Signal(32) # XXX

        bus = self.debug_unit.cpu.debug_bus

        assert write_value.shape() == bus.write_data.shape()


        comb += [
            bus.en.eq(1),
            bus.store.eq(1),
            bus.write_data.eq(write_value),
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
        return # TODO


handlers : dict[int, Type[HandlerDMI]]= {
    DMIReg.DMCONTROL: HandlerDMCONTROL,
    DMIReg.COMMAND: HandlerCOMMAND,
    DMIReg.PROGBUF0: HandlerPROGBUF,
    DMIReg.PROGBUF1: HandlerPROGBUF,
    DMIReg.PROGBUF2: HandlerPROGBUF,
    DMIReg.DATA0: HandlerDATA,
    DMIReg.DATA1: HandlerDATA,
    DMIReg.ABSTRACTAUTO: HandlerABSTRACTAUTO,
}

def shape(layout_cls: data.StructLayout, field: str) -> Shape:
    return data.Layout.cast(layout_cls).members[field]


# Jtag FSM described here:
# https://www.xilinx.com/support/answers/3203.html
class DebugUnit(Elaboratable):
    def __init__(self, cpu):
        self.cpu = cpu
        self.jtag = JTAGTap()
        self.HALT = Signal()

        self.dmi_regs = dict([(k, data.Signal(v)) for k, v in DMI_reg_kinds.items()])

    def elaborate(self, platform):
        m = self.m = Module()
        sync = m.d.sync
        comb = m.d.comb

        m.submodules.jtag = self.jtag

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

        self.HANDLER = Signal()

        self.autoexecdata = Signal(DATASIZE)

        HANDLE_ME_PLZ = 0
        sticky = Signal(reset=HANDLE_ME_PLZ)

        with m.If(jtag_dtmcs.update & jtag_dtmcs.w.dmireset):
            comb += sticky.eq(0) # TODO

        self.csr_regs = dbg_csr_regs
        self.const_csr_values = const_csr_values
        self.nonconst_csr_values = dict([(k, Record(v)) for k, v in self.csr_regs.items() if k not in self.const_csr_values])

        self.controller = ControllerInterface()

        self.dmi_handlers = dict(
            [ 
                ( k, v(
                    my_reg_addr=k,
                    debug_unit=self,
                    dmi_regs=self.dmi_regs,
                    controller=self.controller,
                    write_value=jtag_dmi.w.data) ) for k, v in handlers.items()
            ]
        )

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
                self.dmi_regs[DMIReg.DMSTATUS].version.eq(2),
                self.dmi_regs[DMIReg.DMSTATUS].authenticated.eq(1),

                self.dmi_regs[DMIReg.DMCONTROL].hartsello.eq(1),
                self.dmi_regs[DMIReg.DMCONTROL].hartselhi.eq(0),

                self.dmi_regs[DMIReg.ABSTRACTCS].datacount.eq(1),
                self.dmi_regs[DMIReg.ABSTRACTCS].progbufsize.eq(PROGBUFSIZE),
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
                        sync += jtag_dmi.r.data.eq(record),
                        sync += jtag_dmi.r.op.eq(0), # TODO        

        def on_write(addr, data):
            sync = self.m.d.sync
            sync += self.ONWRITE.eq(1)
            with m.Switch(addr):
                for addr2, record in self.dmi_regs.items():
                    with m.Case(addr2):
                        sync += record.eq(data)
        
        abstractcs : ABSTRACTCS_Layout = self.dmi_regs[DMIReg.ABSTRACTCS]

        with m.FSM() as self.fsm:
            with m.State("IDLE"):
                with m.If(jtag_dmi.update & ~sticky):
                    with m.Switch(jtag_dmi.w.op):
                        with m.Case(DMIOp.NOP):
                            pass
                        with m.Case(DMIOp.READ):
                            on_read(jtag_dmi.w.address)            # moves data from command regs to jtag regs.
                        with m.Case(DMIOp.WRITE):
                            on_write(jtag_dmi.w.address, jtag_dmi.w.data) # takes data from jtag regs into command regs.
                            m.next = "WAIT"
                        sync += abstractcs.busy.eq(jtag_dmi.w.op != DMIOp.NOP)
            with m.State("WAIT"):
                sync += abstractcs.cmderr.eq(self.controller.command_err)
                with m.Switch(jtag_dmi.w.address):
                    for reg, h in self.dmi_handlers.items():
                        with m.Case(reg):
                            h.handle_write()
                with m.If(self.controller.command_finished):
                    m.next = "IDLE"
                    sync += abstractcs.busy.eq(0)

        return m
