#!/usr/bin/env python3

from calc import Calculator
from calc_gentest import gen_test
from nmigen.back.pysim import *

# only 6MHz so that minimum amount of cycles per bit are used
clkfreq = 6000000
baudrate = 1000000

div = round(clkfreq / baudrate)
print(div)

calc = Calculator(clkfreq, baudrate)
sim = Simulator(calc)
sim.add_clock(1/clkfreq)

tests = [
    ('12345', 'ERR LEX'),
    ('#', 'ERR LEX'),
    ('2**2', 'ERR PARSE'),
    ('1/0', 'ERR DIVIDE'),
    ('2+2', '4'),
] 
# + [gen_test() for _ in range(128)]

cur_reply = bytearray()

def test():
    global cur_reply
    fail = False
    yield calc.rxd.eq(1)
    for _ in range(div * 12):
        yield Tick()
    for i, (s, v) in enumerate(tests):
        print(f'TESTING {i}/{len(tests)}')
        for b in s.encode() + b'\n':
            bits = [0, *(b >> i & 1 for i in range(8)), 1]
            for bit in bits:
                # print(bit)
                yield calc.rxd.eq(bit)
                for _ in range(div):
                    # print("tick")
                    yield Tick()
        yield calc.rxd.eq(1)
        while b'\n' not in cur_reply:
            yield Tick()
        i = cur_reply.index(b'\n')
        reply = cur_reply[:i].decode()
        del cur_reply[:i+1]
        if reply != v:
            print(f'MISMATCH: expected {v} got {reply}, test: {s}')
            fail = True
    if not fail:
        print('PASS')

def displ():
    global cur_reply
    yield Passive()
    while True:
        yield Tick()
        yield Settle()
        if not (yield calc.txd):
            for _ in range(div // 2):
                yield Tick()
                yield Settle()
            if (yield calc.txd):
                print('START_ERR')
                sys.exit(1)
            val = 0
            for bit in range(8):
                for _ in range(div):
                    yield Tick()
                    yield Settle()
                val |= (yield calc.txd) << bit
            for _ in range(div):
                yield Tick()
                yield Settle()
            if not (yield calc.txd):
                print('STOP_ERR')
                sys.exit(1)
            cur_reply.append(val)

sim.add_sync_process(test)
sim.add_sync_process(displ)

with sim.write_vcd('calc.vcd'):
    sim.run()
