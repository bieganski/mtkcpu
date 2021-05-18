from typing import Optional
from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.utils.tests.memory import MemoryContents, MemState


def get_sim_memory_test(
    cpu: MtkCpu,
    mem_dict: Optional[MemoryContents],
):
    from nmigen.back.pysim import Passive
    def mem_test():
        yield Passive()
        # yield Tick()
        # yield Settle()
        p = .4  # .5 # probability of mem access in current cycle
        # TODO legacy - not used for now.
        # cursed - if we use state == MemState.FREE instead of list, 'timeout_range' generator wouldn't work.
        # param need to be passed by reference not by value, for actual binding to be visible in each loop iter.
        state = [MemState.FREE]

        arbiter = cpu.arbiter

        while (True):  # that's ok, I'm passive.
            import numpy.random as random

            rdy = random.choice((0, 1), p=[1 - p, p])

            ctr = yield cpu.DEBUG_CTR

            if state[0] == MemState.FREE:
                ack = yield arbiter.bus.ack
                if ack:
                    yield arbiter.bus.ack.eq(0)
                    # print(f"DEBUG_CTR: {ctr}, state: {state[0]}")
                    yield
                    continue
                cyc = yield arbiter.bus.cyc
                we = yield arbiter.bus.we
                write = cyc and we
                read = cyc and not we
                mem_addr = yield arbiter.bus.adr
                if read and write:
                    raise ValueError("ERROR (TODO handle): simultaneous 'read' and 'write' detected.")
                if read:
                    state[0] = MemState.BUSY_READ
                elif write:
                    state[0] = MemState.BUSY_WRITE
                    data = yield arbiter.bus.dat_w
            else:
                if rdy:  # random indicated transaction done in current cycle
                    yield arbiter.bus.ack.eq(1)
                    sel = yield arbiter.bus.sel
                    sel = format(sel, '04b')  # '1111' string for full mask
                    f = lambda x: 0xFF if int(x) == 1 else 0x00
                    g = lambda val, el: (val << 8) + el
                    from functools import reduce
                    mask = reduce(g, map(f, sel))
                    read_val = mem_dict.get_default(mem_addr)
                    if state[0] == MemState.BUSY_WRITE:
                        mem_dict.set(mem_addr, (read_val & ~mask) | (data & mask))
                    elif state[0] == MemState.BUSY_READ:
                        read_val &= mask
                        yield arbiter.bus.dat_r.eq(read_val)
                        # print(f"cyc {ctr}: fetched {read_val} (from {mem_dict})...")
                    state[0] = MemState.FREE
            yield
    return mem_test


def get_sim_register_test(
    name: str,
    cpu: MtkCpu,
    timeout_cycles: int,
    reg_num: Optional[int],
    expected_val: Optional[int],
    default_timeout_extra: int = 25,
):
    from nmigen.back.pysim import Active, Tick, Settle
    check_mem = reg_num is not None

    def reg_test(timeout=default_timeout_extra+timeout_cycles):
        yield Active()
        yield Tick()
        yield Settle()
        print(f"CHECK KURWA {name}")

        for _ in range(timeout):
            en = yield cpu.reg_write_port.en
            if en == 1:
                addr = yield cpu.reg_write_port.addr
                print(f"SPIERDALAJ GEJUJUY CHECK {addr} {reg_num}")
                if addr == reg_num:
                    val = yield cpu.reg_write_port.data
                    if check_mem and (val != expected_val):
                        # TODO that mechanism for now allows for only one write to reg, extend it if neccessary.
                        print(f"== ERROR: Expected data write to reg x{addr} of value {expected_val},"
                              f" got value {val}.. \n== fail test: {name}\n")
                        print(f"{format(expected_val, '32b')} vs {format(val, '32b')}")
                        exit(1)
                    return
            yield Tick()

        if check_mem:
            print(f"== ERROR: Test timeouted! No register write observed. Test: {name}\n")
            exit(1)
    return reg_test
