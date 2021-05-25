from nmigen import *

from mtkcpu.units.debug.jtag import JTAGTap, JtagIR

# Jtag FSM described here:
# https://www.xilinx.com/support/answers/3203.html
class DebugUnit(Elaboratable):
    def __init__(self):
        pass

    def elaborate(self, platform):
        m = Module()
        sync = m.d.sync
        comb = m.d.comb

        self.jtag = m.submodules.jtag = JTAGTap()

        comb += [
            # Spike's openocd config 'exptected-id', see github.com/riscv-isa-sim/README.md
            # self.jtag.regs[JtagIR.IDCODE].r.eq(0x10e31913),
            self.jtag.regs[JtagIR.IDCODE].r.eq(0xdeadbeef),
        ]

        # with m.If(self.jtag.ir == JtagIR.BYPASS):
        #     sync += [
        #         self.jtag.tdo.eq(self.jtag.tdi)
        #     ]

        return m