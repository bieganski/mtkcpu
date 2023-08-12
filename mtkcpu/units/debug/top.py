from typing import overload, Dict
from enum import IntEnum

from mtkcpu.units.debug.jtag import JTAGTap
from mtkcpu.units.debug.types import *
from mtkcpu.units.debug.impl_config import DATASIZE, PROGBUFSIZE
from mtkcpu.units.debug.dmi_handlers import DMI_HANDLERS_MAP, HandlerPROGBUF
from mtkcpu.units.debug.cpu_dm_if import CpuRunningState, CpuRunningStateExternalInterface

from amaranth import *
from amaranth.lib import data

# * The Debug Module’s own state and registers should only 
# be reset at power-up and while dmactive in dmcontrol is 0.


# TODO
# * add 'mark_command_finished' handler's method
# * 'dmi_address' cannot be set independently of main FSM state - eve if in WAIT state


#  If an  exception  is  encountered  during  execution  of  the  Program  Buffer, 
#  no  more  instructions  are executed,  the  hart  remains  in  Debug  Mode,  
#  and cmderr is  set  to  3  (exception error).


class ControllerInterface():
    def __init__(self):
        self.command_err        = Signal(3) # of shape 'cmderr'
        self.command_finished   = Signal()


# Jtag FSM described here:
# https://www.xilinx.com/support/answers/3203.html
class DebugUnit(Elaboratable):
    def __init__(self, cpu):
        self.cpu = cpu
        self.jtag = JTAGTap()
        self.dmi_regs = dict([(k, data.Signal(v)) for k, v in DMI_reg_kinds.items()])

    def elaborate(self, platform):
        m = self.m = Module()
        sync = m.d.sync
        comb = m.d.comb

        m.submodules.jtag = self.jtag

        jtag_dtmcs   = self.jtag.regs[JtagIR.DTMCS]
        jtag_tap_dmi_bus     = self.jtag.regs[JtagIR.DMI]
        jtag_idcode  = self.jtag.regs[JtagIR.IDCODE]

        comb += [
            jtag_idcode.r.eq(JtagIRValue.IDCODE),

            jtag_dtmcs.r.version.eq(JtagIRValue.DM_VERSION),
            jtag_dtmcs.r.abits.eq(JtagIRValue.DM_ABITS),
            jtag_dtmcs.r.dmistat.eq(DMISTAT.NO_ERR),
            jtag_dtmcs.r.idle.eq(2), # TODO
        ]

        self.autoexecdata = Signal(DATASIZE)

        HANDLE_ME_PLZ = 0
        sticky = Signal(reset=HANDLE_ME_PLZ)

        with m.If(jtag_dtmcs.update & jtag_dtmcs.w.dmireset):
            comb += sticky.eq(0) # TODO

        self.controller = ControllerInterface()

        self.dmi_write_value = Signal.like(jtag_tap_dmi_bus.w.data)
        self.dmi_write_address = Signal.like(jtag_tap_dmi_bus.w.address)

        self.dmi_handlers = dict(
            [ 
                ( k, v(
                    my_reg_addr=k,
                    debug_unit=self,
                    dmi_regs=self.dmi_regs,
                    controller=self.controller,
                    dmi_write_value=self.dmi_write_value,
                    dmi_write_address=self.dmi_write_address,) ) for k, v in DMI_HANDLERS_MAP.items()
            ]
        )

        progbuf_handler = HandlerPROGBUF(
            my_reg_addr=-1,
            debug_unit=self,
            dmi_regs=self.dmi_regs,
            controller=self.controller,
            dmi_write_value=self.dmi_write_value,
            dmi_write_address=self.dmi_write_address,
        )

        for i in range(PROGBUFSIZE):
            self.dmi_handlers[DMIReg.PROGBUF0 + i] = progbuf_handler

        def reset():
            self.m.d.sync += [
                self.dmi_regs[DMIReg.DMSTATUS].version.eq(2),
                self.dmi_regs[DMIReg.DMSTATUS].authenticated.eq(1),

                self.dmi_regs[DMIReg.ABSTRACTCS].datacount.eq(DATASIZE),
                self.dmi_regs[DMIReg.ABSTRACTCS].progbufsize.eq(PROGBUFSIZE),
            ]

        reset()

        cpu_state : CpuRunningState = self.cpu.running_state
        cpu_state_if : CpuRunningStateExternalInterface = self.cpu.running_state_interface
        sync += [
            self.dmi_regs[DMIReg.DMSTATUS].allhalted.eq(cpu_state.halted),
            self.dmi_regs[DMIReg.DMSTATUS].anyhalted.eq(cpu_state.halted),
            self.dmi_regs[DMIReg.DMSTATUS].anyrunning.eq(~cpu_state.halted),
            self.dmi_regs[DMIReg.DMSTATUS].allrunning.eq(~cpu_state.halted),
        ]
        with m.If(cpu_state_if.resumeack):
            sync += [
                self.dmi_regs[DMIReg.DMSTATUS].allresumeack.eq(1),
                self.dmi_regs[DMIReg.DMSTATUS].anyresumeack.eq(1),
            ]

        def on_read(addr):
            sync = self.m.d.sync
            with m.Switch(addr):
                for addr2, record in self.dmi_regs.items():
                    with m.Case(addr2):
                        sync += jtag_tap_dmi_bus.r.data.eq(record)
                        sync += jtag_tap_dmi_bus.r.op.eq(0) # TODO
                with m.Default():
                    sync += abstractcs.cmderr.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)

        abstractcs : ABSTRACTCS_Layout = self.dmi_regs[DMIReg.ABSTRACTCS]

        with m.FSM() as self.fsm:
            with m.State("IDLE"):
                with m.If(jtag_tap_dmi_bus.update & ~sticky):
                    with m.Switch(jtag_tap_dmi_bus.w.op):
                        with m.Case(DMIOp.READ):
                            on_read(jtag_tap_dmi_bus.w.address)
                            sync += abstractcs.busy.eq(1)
                            m.next = "DEASSERT_BUSY"
                        with m.Case(DMIOp.WRITE):
                            # TODO - in legacy code for each DMI register we had 'r' and 'w' copy.
                            # Current implementation has only one 'w' register (called 'write_value' in dmi_handlers),
                            # and 'r' for each register. In particular 'on_write' is no longer relevant.
                            # 
                            # That FSM needs to be refactored, but also the way that we automate
                            # the W1/WARL/.../ thing from specs - currently all 'r' fields are set manually.
                            # I postpone that task till the time I better understand system constraints.
                            # Related issue: https://github.com/bieganski/mtkcpu/issues/23
                            #
                            # on_write(jtag_tap_dmi_bus.w.address, jtag_tap_dmi_bus.w.data)
                            sync += abstractcs.busy.eq(1)
                            m.next = "WAIT"

                            sync += [
                                self.dmi_write_value.eq(jtag_tap_dmi_bus.w.data),
                                self.dmi_write_address.eq(jtag_tap_dmi_bus.w.address),
                            ]

                            # TODO
                            # Normally we don't have to latch the written value, and we could discard it
                            # when we set 'self.controller.command_finished', but there is one gotcha.
                            # The ABSTRACTAUTO register that we implement provides interface for triggering
                            # action currently latched in COMMAND.
                            #
                            # To avoid that nasty 'if', issue #23 needs to be implemented.
                            # https://github.com/bieganski/mtkcpu/issues/23
                            # TODO: We lose WARZ property of COMMAND reg here.
                            with m.If(jtag_tap_dmi_bus.w.address == DMIReg.COMMAND):
                                sync += self.dmi_regs[DMIReg.COMMAND].eq(jtag_tap_dmi_bus.w.data)
            with m.State("DEASSERT_BUSY"):
                sync += abstractcs.busy.eq(0)
                m.next = "IDLE"
            with m.State("WAIT"):
                sync += abstractcs.cmderr.eq(self.controller.command_err)
                with m.Switch(self.dmi_write_address):
                    for reg, h in self.dmi_handlers.items():
                        with m.Case(reg):
                            h.handle_write()
                    with m.Default():
                        comb += [
                            self.controller.command_finished.eq(1),
                            self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED),
                        ]
                with m.If(self.controller.command_finished):
                    m.next = "IDLE"
                    sync += abstractcs.busy.eq(0)

        return m
