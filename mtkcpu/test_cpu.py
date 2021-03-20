#!/usr/bin/env python3

from cpu import MtkCpu
from tests.reg_tests import REG_TESTS


def reg_test(name, asm_str, reg_num, exptected_val, timeout_cycles, reg_init, mem_init, verbose=False):
    from io import StringIO
    source_file = StringIO(asm_str)
    from asm_dump import dump_asm

    LOG = lambda x : print(x) if verbose else True

    cpu = MtkCpu(reg_init=reg_init)
    sim = Simulator(cpu)
    sim.add_clock(1e-6)

    from cpu import START_ADDR
    code = dump_asm(source_file, verbose=verbose)
    code_mem_dict = dict([(START_ADDR + 4 * i, c) for i, c in enumerate(code)]) # used by 'test' function
    mem_dict = code_mem_dict.copy()
    mem_dict.update(mem_init)
    if len(code_mem_dict) + len(mem_init) != len(mem_dict):
        raise ValueError(f"ERROR: overlapping memories (instr. mem starting at {START_ADDR} and initial {mem_init})")
    def test():
        yield Tick()
        yield Settle()
        p = .4 # .5 # probability of mem access in current cycle
        from enum import Enum
        class MemState(Enum):
            FREE = 0
            BUSY_READ = 1
            BUSY_WRITE = 2

        # cursed - if we use state == MemState.FREE instead of list, 'timeout_range' geneartor wouldn't work.
        # param need to be passed by reference not by value, for actual binding to be visible in each loop iter.
        state = [MemState.FREE]
        
        def timeout_range(state, test_timeout):
            prev_state = MemState.FREE
            while prev_state == MemState.FREE or state[0] != MemState.FREE:
                prev_state = state[0]
                yield
            for _ in range(test_timeout):
                yield
        
        for _ in timeout_range(state, timeout_cycles + 5):
            ### memory management
            import numpy.random as random

            rdy = random.choice((0, 1), p=[1-p, p])

            if state[0] == MemState.FREE:
                yield cpu.mem.read_vld.eq(1)
                yield cpu.mem.write_vld.eq(1)
                read = yield cpu.mem.read_rdy
                write = yield cpu.mem.write_rdy
                if read and write:
                    raise ValueError("ERROR (TODO handle): simultaneous 'read' and 'write' detected.")
                if read:
                    state[0] = MemState.BUSY_READ
                    addr = yield cpu.mem.read_addr
                elif write:
                    state[0] = MemState.BUSY_WRITE
                    addr = yield cpu.mem.write_addr
                    data = yield cpu.mem.write_data
            else:
                if rdy: # random indicated transaction done in current cycle
                    if state[0] == MemState.BUSY_WRITE:
                        mem_dict[addr] = data
                        yield cpu.mem.write_done.eq(1)
                    elif state[0] == MemState.BUSY_READ:
                        yield cpu.mem.read_data.eq(mem_dict[addr]) # TODO handle error
                        yield cpu.mem.read_done.eq(1)
                    state[0] = MemState.FREE
            ### // memory management
            en = yield cpu.reg_write_port.en
            if en == 1:
                LOG("___ en detected ")
                addr = yield cpu.reg_write_port.addr
                if addr == reg_num:
                    LOG(f"___ got write to reg {addr}...")
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

    print("===== Register tests...")
    for i, t in enumerate(REG_TESTS, 1):
        name = t['name'] if 'name' in t else f"unnamed: \n{t['source']}\n"
        # mem_init = t['mem_init'] if 'mem_init' in t else []
        reg_init = t['reg_init'] if 'reg_init' in t else []
        mem_init = t['mem_init'] if 'mem_init' in t else {}
        reg_test(name, t['source'], t['out_reg'], t['out_val'], t['timeout'], reg_init=reg_init, mem_init=mem_init)
        print(f"== Test {i}/{len(REG_TESTS)}: <{name}> completed successfully..")

    # from minized import MinizedPlatform, TopWrapper
    # m = MtkCpu(32)
    # MinizedPlatform().build(TopWrapper(m), do_program=False)
