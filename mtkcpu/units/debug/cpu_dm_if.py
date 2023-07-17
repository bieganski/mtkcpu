from amaranth import *

class CpuRunningState:
    def __init__(self):
        self.halted      = Signal()
        # self.running     = Signal()
        # self.havereset   = Const(0)
        # self.nonexistent = Const(0)
        # self.unavail     = Const(0)

class CpuRunningStateExternalInterface(Elaboratable):
    def __init__(self):
        # In.
        self.haltreq = Signal()
        self.resumereq = Signal()
        # Out.
        self.resumeack = Signal()
        self.haltack = Signal()

        # Points that module was misused.
        self.error_sticky = Signal()

    def elaborate(self, _):
        m = Module()

        def prev(sig: Signal) -> Signal:
            res = Signal()
            m.d.sync += res.eq(sig)
            return res

        # Only correctness checking for simulation purposes.

        resumeack_takes_two = prev(self.resumeack) & self.resumeack
        haltack_takes_two   = prev(self.haltack)   & self.haltack
        
        haltack_with_no_delay = ~prev(self.haltreq) & self.haltreq & self.haltack
        resumeack_with_no_delay = ~prev(self.resumereq) & self.resumereq & self.resumeack

        with m.If(
            resumeack_takes_two
            | haltack_takes_two
            | haltack_with_no_delay
            | resumeack_with_no_delay
            # NOTE: it is possible to get haltack without prior haltreq,
            # as EBREAK may cause halt as well.
            # | (~self.haltreq & self.haltack) |
            # | (~self.resumereq & self.resumeack)
        ):
            m.d.sync += self.error_sticky.eq(1)

        return m
