from typing import Dict, List, Tuple, AnyStr

from amaranth import *
from amaranth.hdl.rec import DIR_FANIN, DIR_FANOUT, Record
from amaranth.lib.cdc import FFSynchronizer
from amaranth.lib import data

from amaranth.lib.data import Layout

from mtkcpu.units.debug.types import JtagIR, JTAG_IR_regs, IR_DMI_Layout

jtag_layout = [
    ("tck", 1, DIR_FANIN),
    ("tms", 1, DIR_FANIN),
    ("tdi", 1, DIR_FANIN),
    ("tdo", 1, DIR_FANOUT),
]

from typing import Type

def jtagify_dr(type: Type[data.View]) -> data.View:
    """
    TODO: unify with 'reg_make_rw' from top.py.
    """
    layout = data.StructLayout({
        "r": Layout.cast(type),
        "w": Layout.cast(type),
        "update": unsigned(1),
        "capture": unsigned(1),
    })

    return data.Signal(layout)

    

# Jtag FSM described here:
# https://www.xilinx.com/support/answers/3203.html
class JTAGTap(Elaboratable):
    def __init__(
            self, 
            ir_regs : Dict[JtagIR, List[Tuple[AnyStr, int]]] = JTAG_IR_regs, 

            # blind interrogation
            ir_reset=JtagIR.IDCODE.value):

        self.port = Record(jtag_layout)
        self.regs = dict( [(k, jtagify_dr(v)) for k, v in ir_regs.items()] )
        self.ir_reset = ir_reset

        self.jtag_fsm_update_dr = Signal()
        self.jtag_fsm_capture_dr = Signal()

        self.ir = Signal(JtagIR)
        assert self.ir.width == 5 # Spike

        # Use 'UnionLayout' only to delegate signal width calculation.
        _dr_layout = data.UnionLayout({str(k): v for k, v in ir_regs.items()})
        self.dr = Signal(_dr_layout.size)


    def elaborate(self, platform):
        m = Module()
        sync = m.d.sync
        comb = m.d.comb

        # XXX it does nothing but draws a horizontal bar on waveform..
        self.BAR = Signal()
        sync += self.BAR.eq(~self.BAR)

        self.tms = tms = Signal.like(self.port.tms)
        self.tck = tck = Signal.like(self.port.tck)
        self.tdi = tdi = Signal.like(self.port.tdi)
        self.tdo = tdo = Signal.like(self.port.tdo)

        m.submodules += [
            FFSynchronizer(self.port.tms, tms),
            FFSynchronizer(self.port.tck, tck),
            FFSynchronizer(self.port.tdi, tdi),
        ]
        
        prev_tck = Signal()
        self.rising_tck = rising_tck = Signal()
        self.falling_tck = falling_tck = Signal()

        sync += prev_tck.eq(tck)

        comb += [
            rising_tck.eq((~prev_tck) & tck),
            falling_tck.eq(prev_tck & (~tck)),
        ]

        self.tck_ctr = Signal(32)

        with m.If(rising_tck):
            sync += self.tck_ctr.eq(self.tck_ctr + 1)

        # in simulation it's easier to have it in same domain as 'dr' is written, thus 'sync'.
        sync += self.jtag_fsm_update_dr.eq(0)
        sync += self.jtag_fsm_capture_dr.eq(0)

        # Make 'update' bit high only for a single cycle.
        # TODO - move it to combinatorial domain.
        # TODO - without embracing ifs statements it produces undefined behavior in simulation,
        # when driven also from process.
        for ir, record in self.regs.items():
            with m.If(record.update):
                sync += record.update.eq(0)
            with m.If(record.capture):
                sync += record.capture.eq(0)

        with m.FSM() as self.jtag_fsm:
            with m.State("TEST-LOGIC-RESET"):
                with m.If(rising_tck & ~tms):
                    sync += self.ir.eq(self.ir_reset)
                    m.next = "RUN-TEST-IDLE"

            with m.State("RUN-TEST-IDLE"):
                with m.If(rising_tck & tms):
                    m.next = "SELECT-DR-SCAN"

            with m.State("SELECT-DR-SCAN"):
                with m.If(rising_tck):
                    with m.If(tms):
                        m.next = "SELECT-IR-SCAN" # IR path
                    with m.Else():
                        m.next = "CAPTURE-DR" # DR path
            
# DR path
            with m.State("CAPTURE-DR"):
                with m.Switch(self.ir):
                    for ir, record in self.regs.items():
                        with m.Case(ir):
                            sync += self.dr.eq(record.r)
                            with m.If(rising_tck):
                                sync += record.capture.eq(1)
                                sync += self.jtag_fsm_capture_dr.eq(1)
                with m.If(rising_tck):
                    with m.If(tms):
                        m.next = "EXIT1-DR"
                    with m.Else():
                        m.next = "SHIFT-DR"
                        
            with m.State("SHIFT-DR"):
                with m.If(falling_tck):
                    sync += self.port.tdo.eq(self.dr[0])
                with m.Switch(self.ir):
                    for ir, record in self.regs.items():
                        with m.Case(ir):
                            with m.If(rising_tck):
                                # TODO - off by one when calculating 'upper_bound'??
                                upper_bound = Layout.of(record.r).size
                                sync += self.dr.eq(Cat(self.dr[1:upper_bound], tdi))
                with m.If(rising_tck & tms):
                    m.next = "EXIT1-DR"

            with m.State("EXIT1-DR"):
                sync += self.port.tdo.eq(0) # TODO
                with m.If(rising_tck):
                    with m.If(tms):
                        m.next = "UPDATE-DR"
                    with m.Else():
                        m.next = "PAUSE-DR"
            
            with m.State("PAUSE-DR"):
                with m.If(rising_tck & tms):
                    m.next = "EXIT2-DR"

            with m.State("EXIT2-DR"):
                with m.If(rising_tck):
                    with m.If(tms):
                        m.next = "UPDATE-DR"
                    with m.Else():
                        m.next = "SHIFT-DR"

            with m.State("UPDATE-DR"):
                with m.Switch(self.ir):
                    for ir, record in self.regs.items():
                        with m.Case(ir):
                            sync += record.w.eq(self.dr)
                            with m.If(falling_tck):
                                sync += record.update.eq(1)
                                sync += self.jtag_fsm_update_dr.eq(1)
                with m.If(rising_tck):
                    with m.If(tms):
                        m.next = "SELECT-DR-SCAN"
                    with m.Else():
                        m.next = "RUN-TEST-IDLE"

# IR path
            with m.State("SELECT-IR-SCAN"):
                with m.If(rising_tck):
                    with m.If(tms):
                        m.next = "TEST-LOGIC-RESET"
                    with m.Else():
                        m.next = "CAPTURE-IR"

            with m.State("CAPTURE-IR"):
                sync += self.ir.eq(JtagIR.IDCODE)
                with m.If(rising_tck):
                    with m.If(tms):
                        m.next = "EXIT1-IR"
                    with m.Else():
                        m.next = "SHIFT-IR"

            with m.State("SHIFT-IR"):
                with m.If(falling_tck):
                    sync += self.port.tdo.eq(self.ir[0])
                with m.If(rising_tck):
                    sync += self.ir.eq(Cat(self.ir[1:], tdi))
                comb += tdo.eq(self.ir[0])
                with m.If(rising_tck & tms):
                    m.next = "EXIT1-IR"

            with m.State("EXIT1-IR"):
                sync += self.port.tdo.eq(0) # TODO
                with m.If(rising_tck):
                    with m.If(tms):
                        m.next = "UPDATE-IR"
                    with m.Else():
                        m.next = "PAUSE-IR"

            with m.State("PAUSE-IR"):
                with m.If(rising_tck & tms):
                    m.next = "EXIT2-IR"

            with m.State("EXIT2-IR"):
                with m.If(rising_tck & tms):
                    m.next = "UPDATE-IR"
            
            with m.State("UPDATE-IR"):
                with m.If(rising_tck):
                    with m.If(tms):
                        m.next = "SELECT-IR-SCAN"
                    with m.Else():
                        m.next = "RUN-TEST-IDLE"
                
        return m