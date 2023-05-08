from typing import Dict, List, Tuple, AnyStr

from amaranth import *
from amaranth.hdl.rec import DIR_FANIN, DIR_FANOUT, Record, Layout
from amaranth.lib.cdc import FFSynchronizer


from mtkcpu.units.debug.types import JtagIR, JTAG_IR_regs, IR_DMI_Layout

jtag_layout = [
    ("tck", 1, DIR_FANIN),
    ("tms", 1, DIR_FANIN),
    ("tdi", 1, DIR_FANIN),
    ("tdo", 1, DIR_FANOUT),
]

# We either read and write to DR, make it non-overlapping.
def jtagify_dr(layout):
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
        ("capture", 1, DIR_FANOUT),
    ]

    return Layout(res)
    


# Jtag FSM described here:
# https://www.xilinx.com/support/answers/3203.html
class JTAGTap(Elaboratable):
    def __init__(
            self, 
            ir_regs : Dict[JtagIR, List[Tuple[AnyStr, int]]] = JTAG_IR_regs, 

            # blind interrogation
            ir_reset=JtagIR.IDCODE.value):

        self.port = Record(jtag_layout)
        self.regs = dict( [(k, Record(jtagify_dr(v))) for k, v in ir_regs.items()] )
        self.ir_reset = ir_reset


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

        self.ir = Signal(JtagIR)
        assert self.ir.width == 5 # Spike
        self.dr = Signal(max([len(v) for _, v in self.regs.items()]))

        self.DATA_WRITE = Signal(IR_DMI_Layout.total_width())
        self.DATA_READ = Signal.like(self.DATA_WRITE)
        self.DMI_WRITE = Signal(32)

        # TODO
        for ir, record in self.regs.items():
            sync += record.update.eq(0)
            sync += record.capture.eq(0)

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
                            sync += self.DATA_READ.eq(record.r)
                            sync += self.dr.eq(record.r)
                            sync += record.capture.eq(rising_tck)
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
                                sync += self.dr.eq(Cat(self.dr[1:len(record.r)], tdi))
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
                            sync += self.DATA_WRITE.eq(self.dr)
                            with m.If(ir == JtagIR.DMI):
                                sync += self.DMI_WRITE.eq(self.dr[2:34])
                            sync += record.w.eq(self.dr)
                            sync += record.update.eq(falling_tck)
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