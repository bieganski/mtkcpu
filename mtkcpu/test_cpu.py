#!/usr/bin/env python3

from cpu import MtkCpu
from tests.reg_tests import REG_TESTS


def reg_test(name, asm_str, reg_num, exptected_val, timeout_cycles, reg_init=[]):
    from io import StringIO
    source_file = StringIO(asm_str)
    from asm_dump import dump_asm
    cpu = MtkCpu(reg_init=reg_init, mem_init=dump_asm(source_file))

    sim = Simulator(cpu)
    sim.add_clock(1e-6)

    def test():
        yield Tick()
        yield Settle()
        for _ in range(timeout_cycles):
            en = yield cpu.reg_write_port.en
            if en == 1:
                print("___ en detected ")
                addr = yield cpu.reg_write_port.addr
                if addr == reg_num:
                    print(f"___ got write to reg {addr}...")
                    val = yield cpu.reg_write_port.data
                    if val != exptected_val:
                        print(f"== ERROR: Expected data write to reg x{addr} of value {exptected_val}," 
                        f" got value {val}.. \n== fail test: {name}\n")
                        exit(1)
                    return True
            yield Tick()
        print(f"== ERROR: Test timeouted! test: {name}\n")
        exit(1)
    
    sim.add_sync_process(test)
    with sim.write_vcd("cpu.vcd"):
        sim.run()


if __name__ == "__main__":
    from nmigen.back.pysim import *

    from asm_dump import dump_asm
    from io import StringIO

    for t in REG_TESTS:
        name = t['name'] if 'name' in t else f"unnamed: \n{t['source']}\n"
        # mem_init = t['mem_init'] if 'mem_init' in t else []
        reg_init = t['reg_init'] if 'reg_init' in t else []
        reg_test(name, t['source'], t['out_reg'], t['out_val'], t['timeout'], reg_init=reg_init)
        print(f"== Test <{name}> completed successfully..")

    # from minized import MinizedPlatform, TopWrapper
    # m = MtkCpu(32)
    # MinizedPlatform().build(TopWrapper(m), do_program=False)
