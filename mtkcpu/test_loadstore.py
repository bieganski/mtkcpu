import pytest

from nmigen.back.pysim import Simulator, Active, Passive, Tick, Settle
from nmigen import Module
from units.loadstore import LoadStoreUnit, MemoryArbiter


def test_mem_port_unit():
    # m = MtkCpu(reg_init=reg_init)
    arbiter = MemoryArbiter()
    port0 = arbiter.port(priority=0)
    port1 = arbiter.port(priority=1)

    sim = Simulator(arbiter)
    sim.add_clock(1e-6)

    def MAIN():

        yield port0.cyc.eq(1)
        for _ in range(10):
            ack = yield port0.ack
            print(ack)
            yield

    sim.add_sync_process(MAIN)
    with sim.write_vcd("cpu.vcd"):
        sim.run()

