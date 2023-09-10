#!/usr/bin/env python3

from dataclasses import dataclass

from amaranth.sim import Simulator, Settle
from amaranth.lib import data

from mtkcpu.cpu.cpu import MtkCpu, EBRMemConfig
from mtkcpu.utils.tests.dmi_utils import *
from mtkcpu.units.debug.types import *
from mtkcpu.utils.misc import get_color_logging_object
from mtkcpu.cpu.priv_isa import CSRIndex
from mtkcpu.utils.common import MEM_START_ADDR
from mtkcpu.cpu.cpu import CPU_Config
from mtkcpu.units.debug.dmi_handlers import DMI_HANDLERS_MAP
from mtkcpu.units.debug.impl_config import PROGBUFSIZE, PROGBUF_MMIO_ADDR
from mtkcpu.units.debug.impl_config import DATASIZE
from mtkcpu.units.csr_handlers import DCSR

logging = get_color_logging_object()


@dataclass
class DebugUnitSimulationContext:
    cpu: MtkCpu
    dmi_monitor: DMI_Monitor
    simulator: Simulator

def create_simulator() -> DebugUnitSimulationContext:

    ebreak = encode_ins(instructions.Ebreak())

    mem_content_words = [ebreak for _ in range(1000)]
    
    cpu = MtkCpu(
        mem_config=EBRMemConfig(
            mem_size_words=1000,
            mem_content_words=mem_content_words,
            mem_addr=MEM_START_ADDR,
            simulate=True,
        ),
        cpu_config=CPU_Config(
            with_debug=True,
            dev_mode=False,
            pc_reset_value=MEM_START_ADDR,
        )
    )

    dmi_monitor = DMI_Monitor(cpu=cpu)

    simulator = Simulator(fragment=dmi_monitor)
    simulator.add_clock(1e-6)

    return DebugUnitSimulationContext(
        cpu=cpu,
        dmi_monitor=dmi_monitor,
        simulator=simulator,
    )

def dmi_simulator(f):
    def aux(*args, **kwargs):
        assert not args and not kwargs
        context = create_simulator()
        simulator = context.simulator
        cpu = context.cpu
        dmi_monitor = context.dmi_monitor
        from inspect import signature
        names, types = zip(*[(x.name, x.annotation) for x in signature(f).parameters.values()])
        expected_types = [Simulator, MtkCpu, DMI_Monitor]
        if len(types) != 3:
            raise NotImplementedError()
        assert all([x == y for x, y in zip(types[:3], expected_types)])
        print(f"== Starting {f.__name__}")
        f(simulator, cpu, dmi_monitor)
    return aux


@dmi_simulator
def test_dmi_abstract_command_read_write_gpr(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):

    def main_process():
        """
        Write some value to x1, wait, and read x1. Expect to read exactly initial value.
        """
        # Warmup, initial setup.
        yield from activate_DM_and_halt_via_dmi(dmi_monitor=dmi_monitor)

        # Write pattern to DATA0, so that it becomes a payload for further register write.
        # As a result, 'pattern' will be written to 'x1' GPR.
        pattern, regno = 0xdeadbeef, 1
        
        logging.info(f"DMI: Writing {hex(pattern)} to DATA0..")
        yield from dmi_write_data0(dmi_monitor=dmi_monitor, value=pattern)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        # Note that we assume 'update' bit to go down after a single cycle.
        # The relevant logic is expected to be inside Debug Module.
        assert not (yield dmi_monitor.jtag_tap_dmi_bus.update)

        # Make sure that DATA0 does contain 'pattern'.
        data0 = yield cpu.debug.dmi_regs[DMIReg.DATA0].as_value()
        if data0 != pattern:
            raise ValueError(f"DATA0 read: expected {hex(pattern)}, got {hex(data0)}")
        
        # Reset the bus value.
        yield from dmi_bus_reset(dmi_monitor=dmi_monitor)

        # Make the Debug Module write DATA0 content to some CPU GPR, using 'Access Register' abstract command.
        logging.info(f"DMI: Writing DATA0 to x{regno}..")
        yield from dmi_write_access_register_command(
            dmi_monitor=dmi_monitor,
            write=True,
            regno=gpr_to_dmi_access_register_regno(regno),
        )
        yield from few_ticks(5)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)
        yield from few_ticks()

        # Read GPR directly from CPU.
        # TODO - in future CPU should be abstract away, like "DMI_Monitor" abstracts away DM implementation.
        gpr_value = yield cpu.regs._array[1]
        if gpr_value != pattern:
            raise ValueError(f"GRP read: expected {hex(pattern)}, got {hex(gpr_value)}!")
        
        logging.info(f"{hex(pattern)} found in x{regno}!")
        logging.info("Trying to read it via DMI as well..")

        # Make sure that the 'pattern' that we will try to read in a moment
        # is not a remnant after previous op.
        antipattern = pattern // 2
        logging.info(f"DMI: Clobbering DATA0 with {hex(antipattern)}..")
        yield from dmi_bus_reset(dmi_monitor=dmi_monitor)
        yield from dmi_write_data0(dmi_monitor=dmi_monitor, value=antipattern)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)
        yield from few_ticks()
        data0 = yield cpu.debug.dmi_regs[DMIReg.DATA0].as_value()
        if data0 != antipattern:
            raise ValueError(f"DATA0 Clobbering failed: Written {antipattern}, detected {data0} instead!")

        # Now when we clobbered DATA0, read 'x1' to DATA0 and compare with 'pattern'.
        logging.info(f"DMI: Reading x{regno} to DATA0..")
        yield from dmi_bus_reset(dmi_monitor=dmi_monitor)
        yield from dmi_write_access_register_command(
            dmi_monitor=dmi_monitor,
            write=False,
            regno=gpr_to_dmi_access_register_regno(regno),
        )
        yield from few_ticks(5)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        data0 = yield cpu.debug.dmi_regs[DMIReg.DATA0].as_value()
        if data0 != pattern:
            raise ValueError(f"DATA0 read: expected {hex(pattern)}, got {hex(data0)}")

        logging.info(f"Value read via DMI from DATA0 matches x{regno} content!")
    
    processes = [
        main_process,
        *error_monitors(dmi_monitor),
    ]

    for p in processes:
        simulator.add_sync_process(p)

    vcd_traces = [
        # *dmi_monitor.cur_COMMAND_r.fields.values(),
        cpu.debug.jtag.BAR,
        *dmi_monitor.cur_ABSTRACTCS_latched_r.fields.values(),
        cpu.debug.jtag.BAR,
    ]
    
    with simulator.write_vcd("temp.vcd", "temp.gtkw", traces=vcd_traces):
        simulator.run()


@dmi_simulator
def test_dmi_try_read_not_implemented_register(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):

    def main_process():
        """
        RV Debug Specs 1.0-STABLE
        3.15 Debug Module Registers

        When read, unimplemented or non-existent Debug Module DMI Registers return 0.
        Writing them has no effect.
        """

        # Warmup, initial setup.
        yield from few_ticks()
        yield from activate_DM_and_halt_via_dmi(dmi_monitor=dmi_monitor)

        not_implemented_dmi_regs = [0x1, 0x2, 0x3]
        assert not [x for x in not_implemented_dmi_regs if x in DMI_HANDLERS_MAP]

        for dmi_reg in not_implemented_dmi_regs:
            logging.debug(f"Writing dummy value to non-existing DMI register at address {hex(dmi_reg)}")
            yield dmi_monitor.cur_dmi_bus.address.eq(dmi_reg)
            yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
            yield dmi_monitor.cur_dmi_bus.data.eq(0xdeadbeef)
            yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
            yield from dmi_op_wait_for_cmderr(dmi_monitor=dmi_monitor, expected_cmderr=ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)
            yield from clear_cmderr_wait_for_success(dmi_monitor=dmi_monitor)

        for dmi_reg in not_implemented_dmi_regs:
            logging.debug(f"Reading value from non-existing DMI register at address {hex(dmi_reg)}")
            yield dmi_monitor.cur_dmi_bus.address.eq(dmi_reg)
            yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.READ)
            yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
            yield from dmi_op_wait_for_cmderr(dmi_monitor=dmi_monitor, expected_cmderr=ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)
            
            data = yield dmi_monitor.cur_dmi_read_data
            if data != 0x0:
                raise ValueError(f"Expected data=0x0, got {hex(data)}")

    processes = [
        main_process,
        *error_monitors(dmi_monitor),
        print_dmi_transactions(dmi_monitor),
    ]
    
    for p in processes:
        simulator.add_sync_process(p)

    simulator.run()


def cpu_core_is_halted(dmi_monitor: DMI_Monitor):
    return (yield dmi_monitor.cpu.running_state.halted)


@dmi_simulator
def test_core_halt_resume(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):

    def main_process():
        """
        RV Debug specs 1.0-STABLE

        3.5 Run Control

        When a debugger writes 1 to haltreq, each selected hart's halt request bit is set. 
        When a running hart, or a hart just coming out of reset, sees its halt request bit high, 
        it responds by halting, deasserting its running signal, and asserting its halted signal. 
        Halted harts ignore their halt request bit.

        When a debugger writes 1 to resumereq, each selected hart's resume ack bit is cleared 
        and each selected, halted hart is sent a resume request. Harts respond by resuming, 
        clearing their halted signal, and asserting their running signal. At the end of this process
        the resume ack bit is set. These status signals of all selected harts are reflected in 
        allresumeack, anyresumeack, allrunning, and anyrunning. Resume requests are ignored by running harts.
        """

        yield Settle()

        halted = yield from cpu_core_is_halted(dmi_monitor=dmi_monitor)

        if halted:
            raise ValueError("Core halted from the very beginning!")

        yield from activate_DM_and_halt_via_dmi(dmi_monitor=dmi_monitor)

        # Check CPU signal directly first..
        halted = yield from cpu_core_is_halted(dmi_monitor=dmi_monitor)
        if not halted:
            raise ValueError("CPU was not halted after haltreq set!")

        # .. and via DMI
        yield from DMSTATUS_read(dmi_monitor=dmi_monitor)
        
        assert dmi_monitor.cur_dmi_read_data.shape() == unsigned(32)
        data_read_via_dmi = data.View(DMSTATUS_Layout, dmi_monitor.cur_dmi_read_data)
        def check_dmstatus_field_values(fields: Sequence[str], expected: int):
            for x in fields:
                val = yield getattr(data_read_via_dmi, x)
                if val != expected:
                    raise ValueError(f"dmstatus.{x}=={val}, expected {expected}")
        
        halted_expected_low = ["allrunning", "anyrunning", "allresumeack", "anyresumeack"]
        halted_expected_high = ["allhalted", "anyhalted"]
        
        yield from check_dmstatus_field_values(halted_expected_low, 0)
        yield from check_dmstatus_field_values(halted_expected_high, 1)
        
        yield from DMCONTROL_setup_basic_fields(dmi_monitor=dmi_monitor, dmi_op=DMIOp.WRITE)
        yield dmi_monitor.cur_DMCONTROL.haltreq.eq(0)
        yield dmi_monitor.cur_DMCONTROL.resumereq.eq(1)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        yield from DMSTATUS_read(dmi_monitor=dmi_monitor)
        yield from check_dmstatus_field_values(halted_expected_low, 1)
        yield from check_dmstatus_field_values(halted_expected_high, 0)
    
    processes = [
        main_process,
        *error_monitors(dmi_monitor),
        *informative_monitors(dmi_monitor),
        monitor_pc_and_main_fsm(dmi_monitor=dmi_monitor),
    ]

    for p in processes:
        simulator.add_sync_process(p)

    vcd_traces = [
        cpu.just_halted,
        cpu.just_resumed,

        cpu.running_state_interface.haltreq,
        cpu.running_state_interface.haltack,
        cpu.running_state_interface.resumereq,
        cpu.running_state_interface.resumeack,

        cpu.running_state.halted,
    ]
        
    with simulator.write_vcd("halt.vcd", "halt.gtkw", traces=vcd_traces):
        simulator.run()

def clear_cmderr_wait_for_success(dmi_monitor: DMI_Monitor):
    # Note that fields other than 'cmderr' are read-only - we can write FFF..
    busy = yield dmi_monitor.cur_ABSTRACTCS_latched.busy
    assert not busy
    yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.ABSTRACTCS)
    yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
    yield dmi_monitor.cur_dmi_bus.data.eq(0xFFFF_FFFF)
    yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
    yield from dmi_op_wait_for_success(dmi_monitor)

@dmi_simulator
def test_cmderr_clear(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):
    def main_process():
        yield from few_ticks()

        # NOTE: Below line is implementation specific!
        unimplemented_reg = 0x301

        # Try reading some unsupported CSR.
        yield from dmi_write_access_register_command(
            dmi_monitor=dmi_monitor,
            write=True,
            regno=unimplemented_reg,
        )
        yield from few_ticks(5)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from few_ticks()

        # Make sure CMDERR is 2 (meaning 'not supported').
        cmderr = yield dmi_monitor.cur_ABSTRACTCS_latched.cmderr
        if cmderr != ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED:
            raise ValueError(f"Expected cmderr to be {ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED}, got {cmderr} instead!")
    
        # Make sure that writing 0x0 won't clear the cmderr.
        # NOTE that 'cmderr' is the only writable field in 'abstractcs', so don't care about other fields.
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.ABSTRACTCS)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
        yield dmi_monitor.cur_dmi_bus.data.eq(0)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from few_ticks()

        new_cmderr = yield dmi_monitor.cur_ABSTRACTCS_latched.cmderr

        if new_cmderr != cmderr:
            raise ValueError(f"cmderr was expected not to change after 0x0 write (W1C), but it changed from {cmderr} to {new_cmderr}!")
    
        # Finally properly clear it.
        # Once again note that other fields are read-only.
        yield from clear_cmderr_wait_for_success(dmi_monitor=dmi_monitor)

        cmderr = yield dmi_monitor.cur_ABSTRACTCS_latched.cmderr
        if cmderr != ABSTRACTCS_Layout.CMDERR.NO_ERR:
            raise ValueError(f"'cmderr' that is W1C field was not cleared after writing ones! It holds {cmderr} value instead.")

    processes = [
        main_process,
    ]
    
    for p in processes:
        simulator.add_sync_process(p)
        
    simulator.run()

@dmi_simulator
def test_progbuf_writes_to_bus(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):
    assert PROGBUFSIZE >= 2

    memory = dict()

    def main_process():
        yield from few_ticks()

        # Make sure that writing 0x0 won't clear the cmderr.
        # NOTE that 'cmderr' is the only writable field in 'abstractcs', so don't care about other fields.
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.PROGBUF0 + 1)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
        yield dmi_monitor.cur_dmi_bus.data.eq(0xdeadbeef)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor, timeout=1000)

        assert len(memory) == 1
        (addr, val), = memory.items()
        assert addr == PROGBUF_MMIO_ADDR + 4, hex(addr)
        assert val == 0xdeadbeef, hex(val)

    processes = [
        main_process,   
        bus_capture_write_transactions(cpu=cpu, output_dict=memory),
    ]
    
    for p in processes:
        simulator.add_sync_process(p)
        
    simulator.run()


from ppci.arch.riscv import registers, instructions
from riscvmodel.code import decode

def encode_ins(ins: type) -> int:
    import struct
    val = struct.unpack("<I", ins.encode())[0]
    return val

def progbuf_write_wait_for_success(dmi_monitor: DMI_Monitor, progbuf_reg_num: int, ins: type):
    try:
        decoded = decode(ins)
    except Exception:
        decoded = "CAN'T DECODE"
    logging.info(f"PROGBUF: writing {hex(ins)} aka < {decoded} > to {progbuf_reg_num}")
    yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.PROGBUF0 + progbuf_reg_num)
    yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
    yield dmi_monitor.cur_dmi_bus.data.eq(ins)
    yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
    yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor, timeout=1000)
    logging.info(f"PROGBUF written successfully")
        

def trigger_progbuf_exec(dmi_monitor: DMI_Monitor):
    yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.COMMAND)
    yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
    yield dmi_monitor.cur_dmi_bus.data.eq(0)

    yield dmi_monitor.cur_COMMAND.cmdtype.eq(COMMAND_Layout.AbstractCommandCmdtype.AccessRegister)
    acc_reg = dmi_monitor.cur_COMMAND.control

    yield acc_reg.regno.eq(0x1000)
    yield acc_reg.write.eq(0)
    yield acc_reg.transfer.eq(0)
    yield acc_reg.postexec.eq(1)
    yield acc_reg.aarsize.eq(AccessRegisterLayout.AARSIZE.BIT32)
    yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)


@dmi_simulator
def test_halt_resume_with_new_dpc(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):
    
    program_counters_seen : set[int] = set()

    def pc_updater():
        yield Passive()
        while True:
            pc = yield dmi_monitor.cpu.pc
            program_counters_seen.add(pc)
            yield

    def main_process():
        """
        RV Debug specs 1.0-STABLE

        3.5 Run Control

        When a debugger writes 1 to haltreq, each selected hart's halt request bit is set. 
        When a running hart, or a hart just coming out of reset, sees its halt request bit high, 
        it responds by halting, deasserting its running signal, and asserting its halted signal. 
        Halted harts ignore their halt request bit.

        When a debugger writes 1 to resumereq, each selected hart's resume ack bit is cleared 
        and each selected, halted hart is sent a resume request. Harts respond by resuming, 
        clearing their halted signal, and asserting their running signal. At the end of this process
        the resume ack bit is set. These status signals of all selected harts are reflected in 
        allresumeack, anyresumeack, allrunning, and anyrunning. Resume requests are ignored by running harts.
        """

        yield Settle()

        halted = yield from cpu_core_is_halted(dmi_monitor=dmi_monitor)

        if halted:
            raise ValueError("Core halted from the very beginning!")

        yield from activate_DM_and_halt_via_dmi(dmi_monitor=dmi_monitor)

        halted = yield from cpu_core_is_halted(dmi_monitor=dmi_monitor)
        if not halted:
            raise ValueError("CPU was not halted after haltreq set!")
        
        pc = yield dmi_monitor.cpu.pc
        new_pc = pc // 2 + 0x1000
        assert new_pc != pc

        yield dmi_monitor.cpu.csr_unit.reg_by_addr(CSRIndex.DPC).rec.r.eq(new_pc)

        yield from DMCONTROL_setup_basic_fields(dmi_monitor=dmi_monitor, dmi_op=DMIOp.WRITE)
        yield dmi_monitor.cur_DMCONTROL.haltreq.eq(0)
        yield dmi_monitor.cur_DMCONTROL.resumereq.eq(1)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from few_ticks(100)

        if new_pc not in program_counters_seen:
            raise ValueError(f"Was expecting to see PC {hex(new_pc)}, but there were only: {[hex(x) for x in program_counters_seen]}")

    processes = [
        main_process,
        pc_updater,
    ]
    
    for p in processes:
        simulator.add_sync_process(p)
        
    simulator.run()


@dmi_simulator
def test_progbuf_gets_executed(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):
    assert PROGBUFSIZE >= 2

    def main_process():
        yield from few_ticks()

        val = 123
        assert val < 2**11

        gpr_reg_num = 8

        for i, ins in enumerate([
            # addi x1, x0, <val>
            encode_ins(instructions.Addi(registers.get_register(gpr_reg_num), registers.get_register(0), val)),
            encode_ins(instructions.Ebreak()),
        ]):
            yield from progbuf_write_wait_for_success(dmi_monitor, i, ins)

        yield from trigger_progbuf_exec(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_cmderr(
            dmi_monitor=dmi_monitor,
            expected_cmderr=ABSTRACTCS_Layout.CMDERR.HALT_OR_RESUME,
            timeout=1000,
        )
        
        yield from clear_cmderr_wait_for_success(dmi_monitor=dmi_monitor)
        
        yield from activate_DM_and_halt_via_dmi(dmi_monitor=dmi_monitor)
        halted = yield from cpu_core_is_halted(dmi_monitor=dmi_monitor)
        if not halted:
            raise ValueError("CPU was not halted after haltreq set!")
        
        yield from trigger_progbuf_exec(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor, timeout=100)

        x = yield cpu.regs._array._inner[gpr_reg_num]

        if x != val:
            raise ValueError(f"expected x{gpr_reg_num} to contain {hex(val)}, got {hex(x)} instead")

    processes = [
        main_process,
        monitor_cpu_and_dm_state(dmi_monitor=dmi_monitor),
        bus_capture_write_transactions(cpu=cpu, output_dict=dict()),
    ]
    
    for p in processes:
        simulator.add_sync_process(p)
        
    simulator.run()



@dmi_simulator
def test_progbuf_cmderr_on_runtime_error(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):
    assert PROGBUFSIZE >= 2

    def main_process():
        yield from few_ticks()

        invalid_ins = 0xbaad
        yield from progbuf_write_wait_for_success(dmi_monitor, 0, invalid_ins)
        yield from activate_DM_and_halt_via_dmi(dmi_monitor=dmi_monitor)
        yield from trigger_progbuf_exec(dmi_monitor=dmi_monitor)
        
        yield from dmi_op_wait_for_cmderr(
            dmi_monitor=dmi_monitor,
            expected_cmderr=ABSTRACTCS_Layout.CMDERR.EXCEPTION,
            timeout=100,
        )

        halted = yield from cpu_core_is_halted(dmi_monitor=dmi_monitor)
        if not halted:
            raise ValueError("The exception occured during PROGBUF execution. The CMDERR was properly set,"
                             " but the core hasn't halted (hasn't gone into park loop, in specs language).")
    
    def mepc():
        yield Passive()
        while True:
            pc = yield cpu.pc
            mepc = yield cpu.csr_unit.mepc.value
            instr = yield cpu.instr
            print("mepc", hex(mepc), "pc", hex(pc), "instr", hex(instr))
            yield

    processes = [
        main_process,
        monitor_cpu_and_dm_state(dmi_monitor=dmi_monitor),
        bus_capture_write_transactions(cpu=cpu, output_dict=dict()),
        mepc,
    ]
    
    for p in processes:
        simulator.add_sync_process(p)
        
    simulator.run()

@dmi_simulator
def test_access_debug_csr_regs_in_debug_mode(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):
    assert PROGBUFSIZE >= 2
    
    gpr_reg_num = 3

    def main_process():
        yield from few_ticks()

        # TODO: hardcoded 'cause' field offset.
        expected_dcsr_reset_value = DCSR()._reset_value.value | (DCSR_DM_Entry_Cause.HALTREQ << 6)

        DCSR_ins = instructions.RiscvCsrRegister("dcsr", num=0x7b0)

        # 0x7b0021f3
        dcsr_read_ins: int = encode_ins(instructions.Csrr(registers.get_register(gpr_reg_num), DCSR_ins))

        ebreak_ins: int = encode_ins(instructions.Ebreak())

        yield from activate_DM_and_halt_via_dmi(dmi_monitor=dmi_monitor)

        for i, val in enumerate([dcsr_read_ins, ebreak_ins]):
            yield from progbuf_write_wait_for_success(dmi_monitor, i, val)

        yield from trigger_progbuf_exec(dmi_monitor=dmi_monitor)

        prev_reg_content = 0

        for _ in range(timeout := 100):
            reg_content = yield dmi_monitor.cpu.regs._array._inner[gpr_reg_num]
            if reg_content != prev_reg_content:
                logging.info(f"Detected value {hex(reg_content)} written to x{gpr_reg_num}")
                if reg_content != expected_dcsr_reset_value:
                    raise ValueError(f"Was expecting to see {hex(expected_dcsr_reset_value)}, got {hex(reg_content)} instead")
                prev_reg_content = reg_content
                break
            yield
        else:
            raise ValueError(f"Haven't seen write to x{gpr_reg_num} in {timeout} cycles after PROGBUF exec!")

        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor, timeout=100)

    processes = [
        main_process,
        monitor_cpu_and_dm_state(dmi_monitor=dmi_monitor),
        bus_capture_write_transactions(cpu=cpu, output_dict=dict()),
        monitor_writes_to_dcsr(dmi_monitor=dmi_monitor),
    ]
    
    for p in processes:
        simulator.add_sync_process(p)
        
    simulator.run()


@dmi_simulator
def test_not_supported_command_type_finishes(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):
    def main_process():
        yield from activate_DM_and_halt_via_dmi(dmi_monitor=dmi_monitor)
        yield from few_ticks()

        # --- simulation output, that explains '0x2180000' value
        #   INFO     | (mtime=181844)DMI: writing, address: <DMIReg.COMMAND: 23>, 
        # value: 0x2180000 aka 00000010_00011000_00000000_00000000, 
        # dump <class 'mtkcpu.units.debug.types.COMMAND_Layout'>: cmdtype=0x2, 
        # [ <class 'amaranth.lib.data.StructLayout'>: zero2_=0x0, aarsize=0x1, 
        # zero1_=0x1, postexec=0x0, transfer=0x0, write=0x0, regno=0x0 ]
        
        # NOTE: cmdtype=0x2 stands for ACCESS MEMORY abstract command.
        yield dmi_monitor.cur_dmi_bus.data.eq(0x2180000)
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.COMMAND)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)

        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_cmderr(dmi_monitor=dmi_monitor, expected_cmderr=ABSTRACTCS_Layout.CMDERR.NOT_SUPPORTED)
    
    processes = [main_process]
    for p in processes:
        simulator.add_sync_process(p)
        
    simulator.run()

@dmi_simulator
def test_abstracauto_autoexecdata(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):
    def main_process():
        yield from activate_DM_and_halt_via_dmi(dmi_monitor=dmi_monitor)
        yield from few_ticks()

        as_abstractauto: ABSTRACTAUTO_Layout = data.View(ABSTRACTAUTO_Layout, dmi_monitor.cur_dmi_bus.data)
        autoexecdata_width = as_abstractauto.autoexecdata.shape().width

        yield as_abstractauto.autoexecdata.eq(2 ** autoexecdata_width - 1)
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.ABSTRACTAUTO)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)

        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        yield dmi_monitor.cur_dmi_bus.data.eq(0)
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.ABSTRACTAUTO)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.READ)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        actual_data = yield data.View(ABSTRACTAUTO_Layout, dmi_monitor.jtag_tap_dmi_bus.r.data).autoexecdata
        expected_data = 2 ** DATASIZE - 1
        if actual_data != expected_data:
            raise ValueError(f"ABSTRACTAUTO: Was expecting to see {expected_data}, got {actual_data} instead")

        gpr_reg_num = 8

        def get_gpr_value(regno: int):
            assert regno in range(32)
            return (yield cpu.regs._array._inner[regno])
        
        init_reg_value = yield from get_gpr_value(gpr_reg_num)

        for i, ins in enumerate([
            # addi x1, x1, 1
            encode_ins(instructions.Addi(registers.get_register(gpr_reg_num), registers.get_register(gpr_reg_num), 1)),
            encode_ins(instructions.Ebreak()),
        ]):
            yield from progbuf_write_wait_for_success(dmi_monitor, i, ins)
        
        yield from trigger_progbuf_exec(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor, timeout=100)

        reg_value_plus_one = yield from get_gpr_value(gpr_reg_num)

        if init_reg_value + 1 != reg_value_plus_one:
            raise ValueError("Progbuf manual execution seemingly didn't work! Not even trying ABSTRACTAUTO functionality in that case.")
        
        # Any write to DATA0 should trigger latched COMMAND execution - in our case increment value stored in x8.
        yield dmi_monitor.cur_dmi_bus.data.eq(0x12345)
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.DATA0)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        yield from few_ticks(n=3)

        autoexec_reg_value = yield from get_gpr_value(gpr_reg_num)

        if (expected_value := reg_value_plus_one + 1) != autoexec_reg_value:
            raise ValueError(f"ABSTRACTAUTO didn't work, despite the hardware claims that it supports it. Was expecting to see {expected_value}, got {autoexec_reg_value} instead.")
        
        # Now check the autoexec-deassert functionality.
        #
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.ABSTRACTAUTO)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
        yield dmi_monitor.cur_dmi_bus.data.eq(0x0)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        yield dmi_monitor.cur_dmi_bus.data.eq(0x12345)
        yield dmi_monitor.cur_dmi_bus.address.eq(DMIReg.DATA0)
        yield dmi_monitor.cur_dmi_bus.op.eq(DMIOp.WRITE)
        yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
        yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        yield from few_ticks(n=3)

        should_stay_the_same_reg_value = yield from get_gpr_value(gpr_reg_num)

        if should_stay_the_same_reg_value != autoexec_reg_value:
            raise ValueError(f"Despite autoexec was disabled, the hardware seemingly still assumes it is asserted. Expected {autoexec_reg_value}, got {should_stay_the_same_reg_value}")

    processes = [
        main_process,
        monitor_cpu_and_dm_state(dmi_monitor=dmi_monitor),
        monitor_pc_and_main_fsm(dmi_monitor=dmi_monitor),
    ]
    for p in processes:
        simulator.add_sync_process(p)
        
    simulator.run()



@dmi_simulator
def test_ebreakm_halt(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):
    def main_process():

        ebreak = encode_ins(instructions.Ebreak())

        if not all([x == ebreak for x in cpu.mem_config.mem_content_words]):
            raise NotImplementedError("for now only code full of ebreaks supported!")

        def resume_core_via_dmi():
            yield from DMCONTROL_setup_basic_fields(dmi_monitor=dmi_monitor, dmi_op=DMIOp.WRITE)
            yield dmi_monitor.cur_DMCONTROL.haltreq.eq(0)
            yield dmi_monitor.cur_DMCONTROL.resumereq.eq(1)
            yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
            yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        def reset_dmi_bus():
            yield dmi_monitor.cur_dmi_bus.eq(0)

        yield from few_ticks(20) # go to trap
        halted = yield from cpu_core_is_halted(dmi_monitor=dmi_monitor)

        if halted:
            raise ValueError("ebreakm-agnostic bug: Core halted despite resumereq succeeded.")
        
        yield from few_ticks() # XXX
        yield from activate_DM_and_halt_via_dmi(dmi_monitor=dmi_monitor)
        yield from reset_dmi_bus()

        assert (yield from cpu_core_is_halted(dmi_monitor=dmi_monitor))

        yield dmi_monitor.cpu.csr_unit.dcsr.ebreakm.eq(1)
        
        # Starting from now, every EBREAK should cause core halt.

        yield from resume_core_via_dmi()
        halted = yield from cpu_core_is_halted(dmi_monitor=dmi_monitor)
        assert not halted

        for _ in range(timeout := 50):
            halted = yield from cpu_core_is_halted(dmi_monitor=dmi_monitor)
            if halted:
                break # ebreakm did work as expected!
            yield
        else:
            raise ValueError(f"EBREAKM seemingly doesn't have an effect, as core didn't halted during {timeout} cycles!")

    processes = [
        main_process,
        monitor_cpu_and_dm_state(dmi_monitor=dmi_monitor),
        monitor_pc_and_main_fsm(dmi_monitor=dmi_monitor),
        monitor_cmderr(dmi_monitor),
        monitor_cpu_dm_if_error(dmi_monitor),
        bus_capture_write_transactions(cpu=cpu, output_dict=dict()),
    ]
    for p in processes:
        simulator.add_sync_process(p)
    
    simulator.run()


@dmi_simulator
def test_single_step(
    simulator: Simulator,
    cpu: MtkCpu,
    dmi_monitor: DMI_Monitor,
):
    def main_process():

        yield from activate_DM(dmi_monitor=dmi_monitor)

        ebreak = encode_ins(instructions.Ebreak())
        if not all([x == ebreak for x in cpu.mem_config.mem_content_words]):
            raise NotImplementedError("for now only code full of ebreaks supported!")

        def resume_core_via_dmi():
            yield from DMCONTROL_setup_basic_fields(dmi_monitor=dmi_monitor, dmi_op=DMIOp.WRITE)
            yield dmi_monitor.cur_DMCONTROL.haltreq.eq(0)
            yield dmi_monitor.cur_DMCONTROL.resumereq.eq(1)
            yield from dmi_bus_trigger_transaction(dmi_monitor=dmi_monitor)
            yield from dmi_op_wait_for_success(dmi_monitor=dmi_monitor)

        yield from few_ticks(20) # go to trap (that consists of EBREAKs only)
        # make sure that core is still running
        assert not (yield from cpu_core_is_halted(dmi_monitor=dmi_monitor))

        # halt core by decoding EBREAK when 'ebreakm' bit asserted
        yield dmi_monitor.cpu.csr_unit.dcsr.ebreakm.eq(1)
        mtvec = yield dmi_monitor.cpu.csr_unit.mtvec.as_value()
        mem_cfg = cpu.mem_config
        assert mtvec >= mem_cfg.mem_addr
        assert mtvec < mem_cfg.mem_addr + mem_cfg.mem_size_words * mem_cfg.word_size
        yield from few_ticks(20) # go to trap (that consists of EBREAKs only)

        assert (yield from cpu_core_is_halted(dmi_monitor=dmi_monitor))

        yield dmi_monitor.cpu.csr_unit.dcsr.step.eq(1)
        yield
        yield from resume_core_via_dmi()

        assert not (yield from cpu_core_is_halted(dmi_monitor=dmi_monitor))
        for _ in range(20):
            halted = yield from cpu_core_is_halted(dmi_monitor=dmi_monitor)
            if halted:
                return # success! eventually hart halted - single step works as expected

    processes = [
        main_process,
        monitor_cpu_and_dm_state(dmi_monitor=dmi_monitor),
        monitor_pc_and_main_fsm(dmi_monitor=dmi_monitor),
        monitor_cmderr(dmi_monitor),
        monitor_cpu_dm_if_error(dmi_monitor),
        bus_capture_write_transactions(cpu=cpu, output_dict=dict()),
    ]
    for p in processes:
        simulator.add_sync_process(p)
    
    simulator.run()

if __name__ == "__main__":
    # import pytest
    # pytest.main(["-x", __file__])
    test_not_supported_command_type_finishes()
    test_dmi_try_read_not_implemented_register()
    test_dmi_abstract_command_read_write_gpr()
    test_core_halt_resume()
    test_halt_resume_with_new_dpc()
    test_cmderr_clear()
    test_progbuf_writes_to_bus()
    test_progbuf_gets_executed()
    test_progbuf_cmderr_on_runtime_error()
    test_access_debug_csr_regs_in_debug_mode()
    test_abstracauto_autoexecdata()
    test_ebreakm_halt()
    test_single_step()
    logging.critical("ALL TESTS PASSED!")



