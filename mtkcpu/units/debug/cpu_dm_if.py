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

        """
        Interface specifications:

            haltreq: dm_out
            haltack: cpu_out, in at least next cycle after 'haltreq'
            
            resumereq: dm_out
            resumeack: cpu_out, in at least next cycle after 'haltreq'


        
        """

    def elaborate(self, _):
        m = Module()

        return m
