#!/usr/bin/env python3

import logging

logging.basicConfig(level=logging.INFO)
from amaranth import *

from amaranth.lib.wiring import Signature, SignatureMembers, Flow, PureInterface, connect

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

    def __init__(self, max_num_masters: int, bus_shape: Signature, bus_slave: PureInterface) -> None:
        self.num_masters = max_num_masters

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
        m.submodules.pe = self.pe = pe = PriorityEncoder(width=self.num_masters)

        assert len(self.ports) <= self.num_masters

        # reprio. new priorities are guaranteed to be consecutive, starting from 0 (highest)
        tmp = dict()
        for new_prio, (old_prio, v) in enumerate(iter(sorted(self.ports.items()))):
            tmp[new_prio] = v
        self.ports = tmp; del tmp

        # Forward bus ownership requests.
        for k, v in self.ports.items():
            m.d.comb += pe.i[k].eq(v["rq"])

        # Arbitration logic.
        cur_owner = Signal(range(self.num_masters + 1))
        with m.FSM() as self.fsm:
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

class ArbiterTestbench(Elaboratable):
    def __init__(self) -> None:
        pass
    
    def elaborate(self, _):
        m = Module()
        bus_shape = Signature({
            "ready": Flow.In(1),
            "valid": Flow.Out(1),
        })
        bus_slave = bus_shape.flip().create()

        m.submodules.arbiter = self.arbiter = SimpleBusArbiter(
            bus_shape=bus_shape,
            bus_slave=bus_slave,
            max_num_masters=2,
        )

        self.master_low_prio_port = self.arbiter.register_master(priority=123)
        self.master_high_prio_port = self.arbiter.register_master(priority=10)

        return m

dut = ArbiterTestbench()

async def testbench(ctx):
    # Make sure that no false requests are induced by arbiter.
    assert ctx.get(dut.arbiter.pe.none) == 1
    await ctx.tick()
    assert ctx.get(dut.arbiter.pe.none) == 1
    await ctx.tick().repeat(3)
    assert ctx.get(dut.arbiter.pe.none) == 1
    
    # Make sure that higher (the lower number) priority request wins.
    ctx.set(dut.master_low_prio_port["rq"], 1)
    ctx.set(dut.master_high_prio_port["rq"], 1)
    assert ctx.get(dut.arbiter.pe.none) == 0
    assert ctx.get(dut.arbiter.pe.o) == 0
    assert ctx.get(dut.master_high_prio_port["bus_owned"]) == 1

    # Make sure that winner takes bus ownership (in same cycle as 'rq' was set high).
    assert ctx.get(dut.arbiter.bus_slave.valid) == 0
    ctx.set(dut.master_high_prio_port["bus"].valid, 1)
    assert ctx.get(dut.master_high_prio_port["bus"].valid) == 1

    await ctx.tick()

    # Make sure that bus non-owner's signals don't affect arbiter state
    ctx.set(dut.master_low_prio_port["ts_done"], 1)
    await ctx.tick()
    assert ctx.get(dut.arbiter.fsm.state) == 1

    # Make sure that after high prio lets the bus free, the low prio can take it
    assert ctx.get(dut.master_low_prio_port["rq"] ) == 1
    ctx.set(dut.master_high_prio_port["rq"], 0)
    ctx.set(dut.master_high_prio_port["ts_done"], 1)
    await ctx.tick()
    assert ctx.get(dut.master_low_prio_port["bus_owned"]) == 1

if __name__ == "__main__":

    # from amaranth.back import rtlil, verilog
    # from amaranth_boards.icebreaker import ICEBreakerPlatform
    # ICEBreakerPlatform().build(top)
    # with open("top.v", "w") as f:
    #     f.write(verilog.convert(top, ports=[top.sig]))

    from amaranth.sim import Simulator
    sim = Simulator(dut)
    sim.add_clock(1e-6)
    sim.add_testbench(testbench)
# with amaranth_playground.show_waveforms(sim):
# with sim.write_vcd(f"vm.vcd", "vm.gtkw", traces=traces):
    sim.run()
    logging.info("sim ok")