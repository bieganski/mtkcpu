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

        with m.If(self.resumeack):
            m.d.sync += self.resumereq.eq(0)
        
        with m.If(self.haltack):
            m.d.sync += self.haltreq.eq(0)
        
        with m.If(
            (self.haltreq & self.haltack) | (self.resumereq & self.resumeack)
        ):
            m.d.sync += self.error_sticky.eq(1)

        return m
