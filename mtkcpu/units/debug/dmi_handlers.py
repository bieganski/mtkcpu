from amaranth import *

from mtkcpu.units.debug.types import *
from mtkcpu.units.debug.impl_config import PROGBUF_MMIO_ADDR

from amaranth.lib import data
from typing import Type


class ControllerInterfaceDuplicated():
    """
    Duplicated to avoid cyclic import.

    Used only for IDE autocompletion.
    """
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
                 debug_unit,
                 dmi_regs: dict,
                 controller: ControllerInterfaceDuplicated,
                 write_value: Signal,
            ):
        self.debug_unit = debug_unit
        self.dmi_regs = dmi_regs
        self.controller = controller
        self.my_reg_addr = my_reg_addr

        self.reg_dmcontrol      = self.dmi_regs[DMIReg.DMCONTROL]
        self.reg_dmstatus       = self.dmi_regs[DMIReg.DMSTATUS]
        self.reg_command        = self.dmi_regs[DMIReg.COMMAND]
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

        with m.If(self.debug_unit.autoexecdata & (1 << num)):
            # trigger COMMAND handler manually and let it mark command handle finished.
            comb += [
                self.controller.command_finished.eq(1),
                self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.OTHER),
            ]
        with m.Else():
            self.default_handle_write()

class HandlerDMCONTROL(HandlerDMI):

    def handle_write(self):
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb

        write_value = data.View(DMCONTROL_Layout, self.write_value)

        with m.If(self.reg_dmcontrol.dmactive):
            """
            Note that that logic won't be executed when 'dmactive' asserted first time, in the same transaction.
            The proper way is that debugger first writes dmcontrol.dmactive high, then polls dmcontrol until it reads high dmactive.
            """
            # TODO it doesn't take 'hartsel' into account.

            from mtkcpu.units.debug.cpu_dm_if import CpuRunningStateExternalInterface
            cpu_state_if : CpuRunningStateExternalInterface = self.debug_unit.cpu.running_state_interface

            with m.If(write_value.haltreq):
                comb += [
                    cpu_state_if.haltreq.eq(1),
                ]
                with m.If(cpu_state_if.haltack):
                    comb += self.controller.command_finished.eq(1)
            with m.Elif(write_value.resumereq): # Elif, because specs says: 'resumereq is ignored if haltreq is set'
                comb += [
                    cpu_state_if.resumereq.eq(1),
                ]
                with m.If(cpu_state_if.resumeack):
                    comb += self.controller.command_finished.eq(1)
            with m.Else():
                comb += self.controller.command_finished.eq(1)
                
            # Only hart 0 exists.
            hart_different_than_0_was_selected = Cat(write_value.hartselhi, write_value.hartsello).bool()
            sync += [
                self.reg_dmstatus.anynonexistent.eq(hart_different_than_0_was_selected),
                self.reg_dmstatus.allnonexistent.eq(hart_different_than_0_was_selected),
            ]
        with m.Else():
            comb += self.controller.command_finished.eq(1)
        
        # Note that we wait few cycles for req to complete, propagate 'dmactive' to be 
        # available for next DMI WRITE, but not affect current DMI WRITE handling.
        with m.If(self.controller.command_finished):
            sync += self.reg_dmcontrol.dmactive.eq(write_value.dmactive)
        

class HandlerCOMMAND(HandlerDMI):
    def handle_write(self):
        m = self.debug_unit.m
        sync = m.d.sync
        comb = m.d.comb
        
        write_value : COMMAND_Layout = data.View(COMMAND_Layout, self.write_value)

        access_register = COMMAND_Layout.AbstractCommandCmdtype.AccessRegister

        with m.If(write_value.cmdtype == access_register):

            acc_reg = self.acc_reg = write_value.control
            # : AbstractCommandControl.AccessRegisterLayout 
            with m.If(acc_reg.aarsize != AccessRegisterLayout.AARSIZE.BIT32):
                # with m.If(record.postexec | (record.aarsize != 2) | record.aarpostincrement):
                comb += self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)
                comb += self.controller.command_finished.eq(1)
            with m.Else():
                with m.If(acc_reg.transfer):

                    dst = self.debug_unit.dmi_regs[DMIReg.DATA0] # XXX rename
                    # decode register address, as it might be either CSR or GPR
                    with m.If(acc_reg.regno <= 0x0fff):
                        # CSR
                        pass
                        comb += self.controller.command_finished.eq(1)
                        comb += self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)
                        # TODO - I implemented it at some point, but due to the specs it doesn't 
                        # have to be implemented - since we support arbitrary instruction execution via
                        # program buffer, the debugger implementation can read CSRs via csrr instruction.
                        # with m.If(acc_reg.write):
                        #     self.controller.command_finished.eq(1)
                        #     self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)
                        # with m.Switch(acc_reg.regno):
                        #     for addr, _ in self.debug_unit.csr_regs.items():
                        #         with m.Case(addr):
                        #             if addr in self.debug_unit.const_csr_values:
                        #                 with m.If(acc_reg.write):
                        #                     self.controller.command_finished.eq(1)
                        #                     self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)
                        #                 with m.Else():
                        #                     cls = self.debug_unit.const_csr_values[addr]
                        #                     layout = self.debug_unit.csr_regs[addr]
                        #                     sync += dst.eq(cls(layout).to_value())
                        #             else:
                        #                 with m.If(acc_reg.write):
                        #                     self.debug_unit.nonconst_csr_values[addr].eq(write_value)
                        #                 with m.Else():
                        #                     sync += dst.eq(self.debug_unit.nonconst_csr_values[addr])                                    
                                    
                        #     with m.Case(DMI_CSR.DPC):
                        #         sync += dst.eq(self.debug_unit.cpu.pc)
                        # comb += self.controller.command_finished.eq(1)
                    with m.Elif(acc_reg.regno <= 0x101f):
                        # GPR
                        with m.FSM() as self.fsmxd:
                            with m.State("A"):
                                arg0 = self.reg_data0
                                comb += self.debug_unit.cpu.gprf_debug_addr.eq(acc_reg.regno & 0xFF)
                                comb += self.debug_unit.cpu.gprf_debug_write_en.eq(acc_reg.write)
                                with m.If(acc_reg.write):
                                    comb += self.debug_unit.cpu.gprf_debug_data.eq(arg0.as_value())
                                m.next = "B"
                            with m.State("B"):
                                with m.If(~acc_reg.write):
                                    sync += self.reg_data0.eq(self.debug_unit.cpu.gprf_debug_data)
                                m.next = "C"
                            with m.State("C"):
                                m.next = "A"
                                with m.If(~acc_reg.postexec):
                                    comb += self.controller.command_finished.eq(1)
                                with m.Else():
                                    comb += self.controller.command_finished.eq(1)
                                    comb += self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.OTHER)
                                    # execute Program Buffer
                                    # TODO not supported yet.
                                    # sync += self.debug_unit.cpu.pc.eq(PROGBUF_MMIO_ADDR)
                                    pass
                    with m.Else():
                        self.controller.command_finished.eq(1)
                        self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)
                with m.Else():
                    with m.If(~acc_reg.postexec):
                        # no transfer and no postexect bits - not sure what should I do?
                        comb += self.controller.command_finished.eq(1)
                        self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.OTHER)
                    with m.Else():
                        # TODO execute Program Buffer
                        # not yet supported.
                        # TODO - make `dmi_watchdog` cathc CMDERR.OTHER, as its equaivalent of NotImplementedError
                        comb += self.controller.command_finished.eq(1)
                        self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.OTHER)


class HandlerPROGBUF(HandlerDMI):
    def handle_write(self):
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb

        my_idx = self.my_reg_addr - DMIReg.PROGBUF0
        my_mmio_addr = PROGBUF_MMIO_ADDR + 4 * my_idx

        write_value = self.write_value

        self.comb += self.controller.command_finished.eq(1)
        self.comb += self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.OTHER)
        # bus = self.debug_unit.cpu.debug_bus

        # assert write_value.shape() == bus.write_data.shape()

        # comb += [
        #     bus.en.eq(1),
        #     bus.store.eq(1),
        #     bus.write_data.eq(write_value),
        #     bus.addr.eq(my_mmio_addr),
        #     bus.mask.eq(0b1111),
        # ]

        # with m.If(bus.ack):
        #     self.comb += self.controller.command_finished.eq(1)


DMI_HANDLERS_MAP : dict[int, Type[HandlerDMI]]= {
    DMIReg.DMCONTROL: HandlerDMCONTROL,
    DMIReg.COMMAND: HandlerCOMMAND,
    DMIReg.PROGBUF0: HandlerPROGBUF,
    DMIReg.PROGBUF1: HandlerPROGBUF,
    DMIReg.PROGBUF2: HandlerPROGBUF,
    DMIReg.DATA0: HandlerDATA,
    DMIReg.DATA1: HandlerDATA,
}
