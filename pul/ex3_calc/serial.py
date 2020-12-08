from nmigen import *
from nmigen.lib.cdc import FFSynchronizer
from nmigen.utils import bits_for


__all__ = ["AsyncSerialRX", "AsyncSerialTX", "AsyncSerial"]


def _check_parity(parity):
    choices = ("none", "mark", "space", "even", "odd")
    if parity not in choices:
        raise ValueError("Invalid parity {!r}; must be one of {}"
                         .format(parity, ", ".join(choices)))


def _compute_parity_bit(data, parity):
    if parity == "none":
        return C(0, 0)
    if parity == "mark":
        return C(1, 1)
    if parity == "space":
        return C(0, 1)
    if parity == "even":
        return data.xor()
    if parity == "odd":
        return ~data.xor()
    assert False


def _wire_layout(data_bits, parity="none"):
    return [
        ("stop",   1),
        ("parity", 0 if parity == "none" else 1),
        ("data",   data_bits),
        ("start",  1),
    ]


class AsyncSerialRX(Elaboratable):
    def __init__(self, *, divisor, divisor_bits=None, data_bits=8, parity="none", pins=None):
        _check_parity(parity)
        self._parity = parity

        self.divisor = Signal(divisor_bits or bits_for(divisor), reset=divisor)

        self.data = Signal(data_bits)
        self.err  = Record([
            ("overflow", 1),
            ("frame",    1),
            ("parity",   1),
        ])
        self.rdy  = Signal()
        self.ack  = Signal()

        self.i    = Signal(reset=1)

        self._pins = pins

    def elaborate(self, platform):
        m = Module()

        timer = Signal.like(self.divisor)
        shreg = Record(_wire_layout(len(self.data), self._parity))
        bitno = Signal.range(len(shreg))

        if self._pins is not None:
            m.d.submodules += FFSynchronizer(self._pins.rx.i, self.i, reset=1)

        with m.FSM() as fsm:
            with m.State("IDLE"):
                with m.If(~self.i):
                    m.d.sync += [
                        bitno.eq(len(shreg) - 1),
                        timer.eq(self.divisor >> 1),
                    ]
                    m.next = "BUSY"

            with m.State("BUSY"):
                with m.If(timer != 0):
                    m.d.sync += timer.eq(timer - 1)
                with m.Else():
                    m.d.sync += [
                        shreg.eq(Cat(self.i, shreg)),
                        bitno.eq(bitno - 1),
                        timer.eq(self.divisor),
                    ]
                    with m.If(bitno == 0):
                        m.next = "DONE"

            with m.State("DONE"):
                with m.If(self.ack):
                    m.d.sync += [
                        self.data.eq(shreg.data),
                        self.err.frame .eq(~((shreg.start == 0) & (shreg.stop == 1))),
                        self.err.parity.eq(~(shreg.parity ==
                                             _compute_parity_bit(shreg.data, self._parity))),
                    ]
                m.d.sync += self.err.overflow.eq(~self.ack)
                m.next = "IDLE"

        with m.If(self.ack):
            m.d.sync += self.rdy.eq(fsm.ongoing("DONE"))

        return m


class AsyncSerialTX(Elaboratable):
    def __init__(self, *, divisor, divisor_bits=None, data_bits=8, parity="none", pins=None):
        _check_parity(parity)
        self._parity = parity

        self.divisor = Signal(divisor_bits or bits_for(divisor), reset=divisor)

        self.data = Signal(data_bits)
        self.rdy  = Signal()
        self.ack  = Signal()

        self.o    = Signal()

        self._pins = pins

    def elaborate(self, platform):
        m = Module()

        timer = Signal.like(self.divisor)
        shreg = Record(_wire_layout(len(self.data), self._parity))
        bitno = Signal.range(len(shreg))

        if self._pins is not None:
            m.d.comb += self._pins.tx.o.eq(self.o)

        with m.FSM():
            with m.State("IDLE"):
                m.d.comb += self.rdy.eq(1)
                m.d.sync += self.o.eq(shreg[0])
                with m.If(self.ack):
                    m.d.sync += [
                        shreg.start .eq(0),
                        shreg.data  .eq(self.data),
                        shreg.parity.eq(_compute_parity_bit(self.data, self._parity)),
                        shreg.stop  .eq(1),
                        bitno.eq(len(shreg) - 1),
                        timer.eq(self.divisor),
                    ]
                    m.next = "BUSY"

            with m.State("BUSY"):
                with m.If(timer != 0):
                    m.d.sync += timer.eq(timer - 1)
                with m.Else():
                    m.d.sync += [
                        Cat(self.o, shreg).eq(shreg),
                        bitno.eq(bitno - 1),
                        timer.eq(self.divisor),
                    ]
                    with m.If(bitno == 0):
                        m.next = "IDLE"

        return m


class AsyncSerial(Elaboratable):
    def __init__(self, *, divisor, divisor_bits=None, **kwargs):
        self.divisor = Signal(divisor_bits or bits_for(divisor), reset=divisor)

        self.rx = AsyncSerialRX(**kwargs)
        self.tx = AsyncSerialTX(**kwargs)

    def elaborate(self, platform):
        m = Module()
        m.submodules.rx = self.rx
        m.submodules.tx = self.tx
        m.d.comb += [
            self.rx.divisor.eq(self.divisor),
            self.tx.divisor.eq(self.divisor),
        ]
        return m
