#!/usr/bin/env python3

import subprocess
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
from amaranth.back import verilog
from amaranth import *

from amaranth.lib.wiring import Signature, SignatureMembers, Flow, PureInterface, connect

# sig = Signature({
#     "b": Out(2)
# })
# members = SignatureMembers({
#     "a": In(1),
#     "s": Out(sig)
# })
# attrs = members.create()
# self.assertEqual(list(attrs.keys()), ["a", "s"])
# self.assertIsInstance(attrs["a"], Signal)

from amaranth.sim import Simulator
from amaranth.back import rtlil, verilog

class PriorityEncoder(Elaboratable):
    def __init__(self, width):
        self.width = width
        self.i = Signal(self.width)
        self.o = Signal(range(self.width + 1))

        self.none = Signal()

    def elaborate(self, _):
        m = Module()

        for k in reversed(range(self.width)):
            with m.If(self.i[k]):
                m.d.comb += self.o.eq(k)
        m.d.comb += self.none.eq(self.i == 0)  # no requests

        return m

class SimpleBusArbiter(Elaboratable):
    """
    For each bus type, some 'glue logic' is required that will set implement the following:
        * Set the 'rq' bit whenever the bus master requests for the bus ownership, and keep it hight until 'bus_owned' is high.
        * Notify the bus master that it became the bus owner and can proceed with transaction (looking at 'bus_owned') signal.
          Master can drive 'bus' signals in the very same clock cycle as 'bus_owned' went high.
        * Set 'ts_done' bit, meaning that transaction completed. In the very next cycle the bus can be granted to someone else.
    """

    def __init__(self, num_masters: int, bus_shape: Signature, bus_slave: PureInterface) -> None:
        self.num_masters = num_masters

        self.bus_slave = bus_slave
        self.bus_shape = bus_shape

        self.ports = dict()
        self.bus_members = SignatureMembers({
            # Input signals.
            "rq": Flow.In(unsigned(1)),
            "ts_done": Flow.In(unsigned(1)),

            # Output signals.
            "bus_owned": Flow.Out(unsigned(1)),

            "bus": Flow.Out(bus_shape),
        })

    def register_master(self, priority: int) -> dict:
        if priority < 0:
            raise ValueError(f"Negative priority passed! {priority} < 0.")
        if priority in self.ports:
            raise ValueError(
                f"Conflicting priority passed to MemoryArbiter.port(): {priority}"
            )
        port = self.ports[priority] = self.bus_members.create()
        return port

    def elaborate(self, _):
        m = Module()
        m.submodules += (pe := PriorityEncoder(width=self.num_masters))

        cur_owner = Signal(range(self.num_masters + 1))

        # Forward bus ownership requests.
        for k, v in enumerate(self.ports.values()):
            m.d.comb += pe.i[k].eq(v["rq"])

        # Arbitration logic.
        with m.FSM():
            with m.State("IDLE"):
                
                with m.If(~pe.none):
                    m.next = "TS_IN_PROGRESS"
                    for k, v in self.ports.items():
                        with m.If(k == pe.o):
                            m.d.comb += v["bus_owned"].eq(1),
                            m.d.sync += cur_owner.eq(k)
                            connect(m, self.bus_slave, v["bus"])
            with m.State("TS_IN_PROGRESS"):
                for k, v in self.ports.items():
                    with m.If((k == cur_owner) & (v["ts_done"])):
                        m.next = "IDLE"
        return m

class Top(Elaboratable):
    def __init__(self) -> None:
        pass
    
    def elaborate(self, _):
        m = Module()
        bus_shape = Signature({
            "ready": Flow.In(1),
            "valid": Flow.Out(1),
        })
        bus_slave = bus_shape.flip().create()

        m.submodules.arbiter = arbiter = SimpleBusArbiter(
            bus_shape=bus_shape,
            bus_slave=bus_slave,
            num_masters=2,
        )

        self.master0_port = arbiter.register_master(priority=0)
        self.master1_port = arbiter.register_master(priority=1)

        return m

top = Top()

# from amaranth_boards.icebreaker import ICEBreakerPlatform
# ICEBreakerPlatform().build(top)
# with open("top.v", "w") as f:
#     f.write(verilog.convert(top, ports=[top.sig]))


async def testbench(ctx):
    for _ in range(10):
        await ctx.tick()
        print(f"count: {ctx}")

sim = Simulator(top)
sim.add_clock(1e-6)
sim.add_testbench(testbench)
# with amaranth_playground.show_waveforms(sim):
# with sim.write_vcd(f"vm.vcd", "vm.gtkw", traces=traces):
sim.run()