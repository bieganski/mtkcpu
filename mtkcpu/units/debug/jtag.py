from nmigen import *
from nmigen.hdl.rec import DIR_FANIN, DIR_FANOUT, Record, Layout
from nmigen.lib.cdc import FFSynchronizer

from enum import IntEnum
from typing import Dict, List, Tuple, AnyStr

jtag_layout = [
    ("tck", 1, DIR_FANIN),
    ("tms", 1, DIR_FANIN),
    ("tdi", 1, DIR_FANIN),
    ("tdo", 1, DIR_FANOUT),
]
# Spike's irlen == 5
class JtagIR(IntEnum):
    BYPASS = 0b11111
    IDCODE = 0b00010
    CUSTOM = 0b10100


dr_regs = {
    JtagIR.IDCODE: [
        ("value", 32)
    ],
    JtagIR.CUSTOM: [
        ("a", 11),
        ("b", 19),
    ]
}

# We either read and write to DR, make it non-overlapping.
def jtagify_dr(layout):
    assert all(len(x) == 2 for x in layout) or all(len(x) == 3 for x in layout)

    def f(x):
        if len(x) == 2:
            return tuple([*x, DIR_FANOUT])
        else:
            return x
    
    res = [
        ("r", list(map(f, layout))),
        ("w", list(map(f, layout))),
    ]

    return Layout(res)
    


# Jtag FSM described here:
# https://www.xilinx.com/support/answers/3203.html
class JTAGTap(Elaboratable):
    def __init__(
            self, 
            regs : Dict[JtagIR, List[Tuple[AnyStr, int]]] = dr_regs, 

            # blind interrogation
            ir_reset=JtagIR.IDCODE.value):

        self.port = Record(jtag_layout)
        self.regs = dict( [(k, Record(jtagify_dr(v))) for k, v in regs.items()] )
        self.ir_reset = ir_reset


    def elaborate(self, platform):
        m = Module()
        sync = m.d.sync
        comb = m.d.comb

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

        self.TDO = Signal(64, reset=0)

        self.ir = Signal(JtagIR)
        assert self.ir.width == 5 # Spike
        self.dr = Signal(max([len(v) for _, v in self.regs.items()]))

        with m.FSM() as jtag_fsm:
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
                    with m.If(tms):
                        m.next = "EXIT1-DR"
                    with m.Else():
                        m.next = "SHIFT-DR"
                        
            with m.State("SHIFT-DR"):
                with m.If(falling_tck):
                    sync += self.port.tdo.eq(self.dr[0])
                    sync += self.TDO.eq(Cat(self.TDO[1:], self.dr[0]))
                with m.Switch(self.ir):
                    for ir, record in self.regs.items():
                        with m.Case(ir):
                            with m.If(rising_tck):
                                sync += self.dr.eq(Cat(self.dr[1:len(record.r)], tdi))
                # below is not enough, as it may effect in garbage 
                # sync += self.dr.eq(Cat(self.dr[1:], tdi))
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
                sync += self.ir.eq(0b00001)
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