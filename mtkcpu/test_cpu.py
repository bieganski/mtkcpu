#!/usr/bin/env python3

from cpu import MtkCpu
from tests.reg_tests import REG_TESTS

# checks performed: 
# * if 'expected_val' is not None: check if x<'reg_num'> == 'expected_val',
# * if 'expected_mem' is not None: check if for all k, v in 'expected_mem.items()' mem[k] == v.
def reg_test(name, asm_str, timeout_cycles, reg_num, exptected_val, expected_mem, reg_init, mem_init, verbose=False):
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

    assert((reg_num is None and expected_val is None) or (reg_num is not None and exptected_val is not None))
    check_reg = reg_num is not None
    check_mem = expected_mem is not None
    caught_reg_val = None

    def TEST_MAIN():
        global caught_reg_val
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

        cyc = 0
        for _ in timeout_range(state, timeout_cycles + 5):
            cyc += 1
            ### memory management
            import numpy.random as random

            rdy = random.choice((0, 1), p=[1-p, p])

            if state[0] == MemState.FREE:
                yield cpu.ibus.mem_port.ack.eq(0) # TODO potrzebne?
                cyc = yield cpu.ibus.mem_port.cyc
                we = yield cpu.ibus.mem_port.we
                write = cyc and     we 
                read  = cyc and not we
                mem_addr = yield cpu.ibus.mem_port.adr
                if read and write:
                    raise ValueError("ERROR (TODO handle): simultaneous 'read' and 'write' detected.")
                if read:
                    state[0] = MemState.BUSY_READ
                elif write:
                    state[0] = MemState.BUSY_WRITE
                    data = yield cpu.ibus.mem_port.dat_w
            else:
                if rdy: # random indicated transaction done in current cycle
                    yield cpu.ibus.mem_port.ack.eq(1)
                    if state[0] == MemState.BUSY_WRITE:
                        mem_dict[mem_addr] = data # TODO implement select
                    elif state[0] == MemState.BUSY_READ:
                        yield cpu.ibus.mem_port.dat_r.eq(mem_dict[mem_addr]) # TODO handle error
                        # print(f"cyc {cyc}: fetched {mem_dict[mem_addr]} (from {mem_dict})...")
                    state[0] = MemState.FREE
            ### // memory management
            en = yield cpu.reg_write_port.en
            if en == 1:
                LOG("___ en detected ")
                addr = yield cpu.reg_write_port.addr
                if addr == reg_num:
                    LOG(f"___ got write to reg {addr}...")
                    val = yield cpu.reg_write_port.data
                    caught_reg_val = val
                    if check_reg and (val != exptected_val):
                        # TODO that mechanism for now allows for only one write to reg, extend it if neccessary.
                        print(f"== ERROR: Expected data write to reg x{addr} of value {exptected_val}," 
                        f" got value {val}.. \n== fail test: {name}\n")
                        exit(1)
                    break # we may want to also check memory
            yield Tick()
        if check_reg and caught_reg_val is None:
            print(f"== ERROR: Test timeouted! No register write observed. Test: {name}\n")
            exit(1)
        if check_mem:
            for k, v in expected_mem.items():
                if not k in mem_dict:
                    print(f"Errorr! Wrong memory state. Expected {v} value in {k} addr, got nothing here!")
                    exit(1)
                if mem_dict[k] != v:
                    print(f"Errorr! Wrong memory state. Expected {v} value in {k} addr, got {mem_dict[k]}")
                    exit(1)
    
    sim.add_sync_process(TEST_MAIN)
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
        out_reg  = t['out_reg']  if 'out_reg'  in t else None
        out_val  = t['out_val']  if 'out_val'  in t else None
        out_mem  = t['out_mem']  if 'out_mem'  in t else None
        reg_test(
            name=name, 
            asm_str=t['source'], 
            timeout_cycles=t['timeout'], 
            reg_num=out_reg, 
            exptected_val=out_val, 
            expected_mem=out_mem, 
            reg_init=reg_init,
            mem_init=mem_init,
            verbose=False)
        print(f"== Test {i}/{len(REG_TESTS)}: <{name}> completed successfully..")

    # from minized import MinizedPlatform, TopWrapper
    # m = MtkCpu(32)
    # MinizedPlatform().build(TopWrapper(m), do_program=False)
