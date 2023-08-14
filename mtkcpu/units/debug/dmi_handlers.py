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
class HandlerDMI(Elaboratable):
    def __init__(self,
                 my_reg_addr: int,
                 debug_unit,
                 dmi_regs: dict,
                 controller: ControllerInterfaceDuplicated,
                 dmi_write_value: Signal,
                 dmi_write_address: Signal,
            ):
        self.debug_unit = debug_unit
        self.dmi_regs = dmi_regs
        self.controller = controller

        # -- Input signals
        # 
        # Needs to be deasserted in cycle following 'controller.cmd_finished' asserted.
        self.active = Signal()

        # TODO
        # https://github.com/bieganski/mtkcpu/issues/25
        self.my_reg_addr = my_reg_addr
        self.dmi_write_address = dmi_write_address

        self.reg_dmcontrol      = self.dmi_regs[DMIReg.DMCONTROL]
        self.reg_dmstatus       = self.dmi_regs[DMIReg.DMSTATUS]
        self.reg_command        = self.dmi_regs[DMIReg.COMMAND]
        self.reg_abstractcs     = self.dmi_regs[DMIReg.ABSTRACTCS]
        self.reg_data0          = self.dmi_regs[DMIReg.DATA0]

        assert dmi_write_value.shape() == unsigned(32)
        self.write_value = dmi_write_value
    

    def elaborate(self):
        raise NotImplementedError()
    

class HandlerDATA(HandlerDMI):
    def elaborate(self, _):
        m = Module()
        sync, comb = m.d.sync, m.d.comb
        num = self.my_reg_addr - DMIReg.DATA0

        with m.If(self.active):
            with m.FSM() as self.fixme_fsm:
                with m.State("LATCH"):
                    my_reg = self.debug_unit.dmi_regs[self.my_reg_addr]
                    sync += [
                        my_reg.eq(self.write_value),
                    ]
                    m.next = "MAYBE_TRIGGER_COMMAND_EXEC"
                with m.State("MAYBE_TRIGGER_COMMAND_EXEC"):
                    with m.If(self.debug_unit.dmi_regs[DMIReg.ABSTRACTAUTO].autoexecdata & (1 << num)):
                        # NOTE: current implementation assumes that all implemented DATAx support autoexecdata.
                        # FIXME - it duplicates the logic of 'handle_write'.
                        
                        # trigger COMMAND handler manually and let it mark command handle finished.
                        #
                        # self.debug_unit.dmi_handlers[DMIReg.COMMAND].handle_write()
                        # with m.If(self.controller.command_finished):
                        #     m.next = "LATCH"
                        m.next = "LATCH" # FIXME FIXME FIXME only temporarily.
                        comb += self.controller.command_finished.eq(1) # FIXME FIXME FIXME
                    with m.Else():
                        m.next = "LATCH"
                        comb += self.controller.command_finished.eq(1)
        return m

class HandlerABSTRACTCS(HandlerDMI):
    def elaborate(self, _):
        m = Module()
        comb, sync = m.d.comb, m.d.sync

        write_value = data.View(ABSTRACTCS_Layout, self.write_value)

        with m.If(self.active):
            # Related issue: https://github.com/bieganski/mtkcpu/issues/23
            comb += self.controller.command_finished.eq(1)
            sync += self.reg_abstractcs.cmderr.eq(
                self.reg_abstractcs.cmderr & (~write_value.cmderr)
            )

        return m

class HandlerDMCONTROL(HandlerDMI):
    def elaborate(self, _):
        m = Module()
        comb, sync = m.d.comb, m.d.sync

        write_value = data.View(DMCONTROL_Layout, self.write_value)

        with m.If(self.active):
            with m.If(self.reg_dmcontrol.dmactive):
                """
                Note that that logic won't be executed when 'dmactive' asserted first time, in the same transaction.
                The proper way is that debugger first writes dmcontrol.dmactive high, then polls dmcontrol until it reads high dmactive.
                """
                # TODO it doesn't take 'hartsel' into account.

                from mtkcpu.units.debug.cpu_dm_if import CpuRunningStateExternalInterface
                cpu_state_if : CpuRunningStateExternalInterface = self.debug_unit.cpu.running_state_interface

                with m.If(write_value.haltreq & ~self.debug_unit.cpu.running_state.halted):
                    comb += [
                        cpu_state_if.haltreq.eq(1),
                    ]
                    with m.If(cpu_state_if.haltack):
                        comb += self.controller.command_finished.eq(1)
                with m.Elif(write_value.resumereq & self.debug_unit.cpu.running_state.halted):
                    # NOTE: Elif, because specs says: 'resumereq is ignored if haltreq is set'
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

        return m
        

class HandlerCOMMAND(HandlerDMI):
    def elaborate(self, _):
        m = Module()
        comb, sync = m.d.comb, m.d.sync
        
        # NOTE: 'write_value' is slightly different in COMMAND handler, as it uses value 
        # just latched in main handler-picking Switch statement (temporary solution).
        write_value : COMMAND_Layout = data.View(COMMAND_Layout, self.dmi_regs[DMIReg.COMMAND])

        with m.If(self.active):
            with m.If(write_value.cmdtype == COMMAND_Layout.AbstractCommandCmdtype.AccessRegister):
                with m.FSM() as self.main_fms:
                    with m.State("TRANSFER"):
                        
                        next = self.next = Signal()

                        acc_reg = self.acc_reg = write_value.control
                        with m.If(acc_reg.transfer):
                            # decode register address, as it might be either CSR or GPR
                            # TODO inefficient logic.. use 'matches' instead.

                            with m.If(acc_reg.aarsize != AccessRegisterLayout.AARSIZE.BIT32):
                                # From specs:
                                # This bit [transfer] can be used to just execute the Program Buffer without having to
                                # worry about placing valid values into aarsize or regno.

                                # with m.If(record.postexec | (record.aarsize != 2) | record.aarpostincrement):
                                comb += self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)
                                comb += self.controller.command_finished.eq(1)
                            with m.Else():
                                with m.If((acc_reg.regno >= 0x1000) & (acc_reg.regno <= 0x101f)):
                                    # GPR
                                    with m.FSM():
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
                                            m.next = "A"
                                            comb += next.eq(1)
                                with m.Else():
                                    comb += [
                                        self.controller.command_finished.eq(1),
                                        self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)
                                    ]
                        with m.Else():
                            comb += next.eq(1)

                        with m.If(next):
                            m.next = "POSTEXEC"
                    
                    with m.State("POSTEXEC"):
                        done = Signal() # drive outer FSM state from inner FSM.

                        with m.If(done):
                            comb += self.controller.command_finished.eq(1)
                            m.next = "TRANSFER"

                        with m.If(~acc_reg.postexec):
                            comb += done.eq(1)
                        with m.Else():
                            from mtkcpu.cpu.cpu import MtkCpu
                            from mtkcpu.cpu.priv_isa import CSRIndex
                            cpu : MtkCpu = self.debug_unit.cpu
                            real_dpc = Signal(32)
                            dpc = cpu.csr_unit.reg_by_addr(CSRIndex.DPC).rec.r
                            with m.FSM():
                                with m.State("SANITY_CHECK"):
                                    with m.If(~self.debug_unit.cpu.running_state.halted):
                                        comb += self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.HALT_OR_RESUME)
                                        comb += done.eq(1)
                                    with m.Else():
                                        m.next = "A"
                                with m.State("A"):
                                    sync += [
                                        real_dpc.eq(dpc),
                                        cpu.is_debug_mode.eq(1),
                                    ]
                                    m.next = "B"
                                with m.State("B"):
                                    sync += [
                                        # TODO: encapsulation - we shouldn't write to CPU CSR directly from DM.
                                        dpc.eq(PROGBUF_MMIO_ADDR)
                                    ]
                                    m.next = "C"
                                with m.State("C"):
                                    comb += cpu.running_state_interface.resumereq.eq(1)
                                    with m.If(cpu.running_state_interface.resumeack):
                                        m.next = "D"
                                        sync += dpc.eq(real_dpc) # TODO - is that a proper place for that assign?
                                with m.State("D"):
                                    with m.If(cpu.running_state.halted):
                                        # CPU executed ebreak.
                                        comb += done.eq(1)
                                        m.next = "SANITY_CHECK"
                                        sync += cpu.is_debug_mode.eq(0)
                                    
                                    # NOTE: Slippery here.
                                    with m.Elif(cpu.running_state_interface.error_on_progbuf_execution):
                                        # Exception occured during PROGBUF execution. 
                                        comb += done.eq(1)
                                        m.next = "SANITY_CHECK"

                                        comb += self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.EXCEPTION)
            with m.Else():
                comb += [
                    self.controller.command_err.eq(ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED),
                    self.controller.command_finished.eq(1),
                ]
        return m
                    


class HandlerPROGBUF(HandlerDMI):
    def elaborate(self, _):
        m = Module()
        comb, sync = m.d.comb, m.d.sync

        # https://github.com/bieganski/mtkcpu/issues/25
        assert self.my_reg_addr < 0  # make sure we won't use it here, as it would be invalid.

        with m.If(self.active):
            my_mmio_addr = Signal(32)
            comb += my_mmio_addr.eq(PROGBUF_MMIO_ADDR + ((self.dmi_write_address - DMIReg.PROGBUF0) << 2))

            bus = self.debug_unit.cpu.debug_bus
            assert self.write_value.shape() == bus.write_data.shape()

            comb += [
                bus.en.eq(1),
                bus.store.eq(1),
                bus.write_data.eq(self.write_value),
                bus.addr.eq(my_mmio_addr),
                bus.mask.eq(0b1111),
            ]

            with m.If(bus.ack):
                comb += self.controller.command_finished.eq(1)

        return m

class HandlerABSTRACTAUTO(HandlerDMI):
    def elaborate(self, _):
        m = Module()
        return m
    def handle_write(self):
        m = self.debug_unit.m
        sync = self.sync
        comb = self.comb

        from mtkcpu.units.debug.impl_config import DATASIZE
        AUTOEXEC_NUM_SUPPORTED_DATA_BITS = DATASIZE # autoexec is implemented for all bits.

        write_value      : ABSTRACTAUTO_Layout = data.View(ABSTRACTAUTO_Layout, self.write_value)
        reg_abstractauto : ABSTRACTAUTO_Layout = data.View(ABSTRACTAUTO_Layout, self.dmi_regs[DMIReg.ABSTRACTAUTO])

        self.comb += self.controller.command_finished.eq(1)

        # WARL.
        self.sync += [
            reg_abstractauto.autoexecdata[:AUTOEXEC_NUM_SUPPORTED_DATA_BITS].eq(write_value.autoexecdata[:AUTOEXEC_NUM_SUPPORTED_DATA_BITS]),
        ]
        

DMI_HANDLERS_MAP : dict[int, Type[HandlerDMI]]= {
    DMIReg.DMCONTROL: HandlerDMCONTROL,
    DMIReg.COMMAND: HandlerCOMMAND,
    DMIReg.DATA0: HandlerDATA,
    DMIReg.DATA1: HandlerDATA,
    DMIReg.ABSTRACTCS: HandlerABSTRACTCS,
    DMIReg.ABSTRACTAUTO: HandlerABSTRACTAUTO,

    # NOTE:
    # HandlerPROGBUFx is not stated here.
}
