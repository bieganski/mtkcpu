from nmigen import *

from reader import Reader
from writer import Writer
from target import TargetWrapper


class Accelerator(Elaboratable):
    def __init__(self, axi_tgt, axi_ini):
        self.axi_tgt = axi_tgt
        self.axi_ini = axi_ini

    def elaborate(self, platform):
        m = Module()

        m.submodules.target = target = TargetWrapper(self.axi_tgt)
        m.submodules.reader = reader = Reader(self.axi_ini)
        m.submodules.writer = writer = Writer(self.axi_ini)

        # ...

        return m
