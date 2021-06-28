import socket
from functools import reduce
from subprocess import TimeoutExpired
from time import time
from typing import Optional
from enum import Enum
from nmigen.hdl.ast import Signal
from nmigen.back.pysim import Active, Settle, Tick, Passive
from nmigen.hdl.ir import Elaboratable, Fragment


from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.utils.tests.memory import MemoryContents, MemState
# from mtkcpu.utils.tests.utils import find_fsm


def find_fsm(top, *path):
    assert isinstance(top, Elaboratable)
    # ugly hack for retrieving jtag FSM state for 'traces=vcd_traces' variable
    # https://freenode.irclog.whitequark.org/nmigen/2020-07-26#27592720;
    frag = Fragment.get(top, platform=None)
    fsm = frag.find_generated(*path) 
    # returned fsm instance has got attributes "state" (for current state signal) and "encoding" for state names mapping 
    return fsm

HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 9824        # Port to listen on (non-privileged ports are > 1023)


# =============== from openOCD documentation:
# B - Blink on
# b - Blink off
# R - Read request
# Q - Quit request
# 0 - Write 0 0 0
# 1 - Write 0 0 1
# 2 - Write 0 1 0
# 3 - Write 0 1 1
# 4 - Write 1 0 0
# 5 - Write 1 0 1
# 6 - Write 1 1 0
# 7 - Write 1 1 1
# r - Reset 0 0
# s - Reset 0 1
# t - Reset 1 0
# u - Reset 1 1
class OcdCommand(Enum):
    SAMPLE = b'R'
    QUIT = b'Q'
    BLINK_ON = b"B"
    BLINK_OFF = b"b"
    RESET = b"r"
    # RESET = 

    # @classmethod
    def skip(self):
        return self.value in [OcdCommand.BLINK_ON.value, OcdCommand.BLINK_OFF.value]

# TODO
# after https://www.python.org/dev/peps/pep-0622/
# unify JTAGInput and OcdCommand.
class JTAGInput():
    def __init__(self, ocd_bitbang_val):
        self.tck = int(ocd_bitbang_val & 0x4 != 0)
        self.tms = int(ocd_bitbang_val & 0x2 != 0)
        self.tdi = int(ocd_bitbang_val & 0x1 != 0)
    
    def __repr__(self):
        return f"TCK: {self.tck}, TMS: {self.tms}, TDI: {self.tdi}"

    # cursed
    def skip(self):
        return False



def decode_cmd(char):
    # from openocd/.../remote_bitbang.c
    # char c = '0' + ((tck ? 0x4 : 0x0) | (tms ? 0x2 : 0x0) | (tdi ? 0x1 : 0x0));
    if ord(char) < ord('8') and ord(char) >= ord('0'):
        return JTAGInput(ord(char) - ord('0'))
    return OcdCommand(char)
        
def remote_jtag_get_cmd(conn):
    while True:
        data = conn.recv(1)
        # print(f"data: {data}")
        if not data:
            break
        cmd = decode_cmd(data)
        # print(cmd)
        if cmd.skip():
            continue
        yield cmd

def AAA(conn):
    data = conn.recv(1)
    cmd = decode_cmd(data)
    return cmd


def remote_jtag_send_response(conn, tdo):
    if type(tdo) != bytes:
        raise ValueError(f"remote_jtag_send_response: 'tdo' must be bytes instance, not {type(tdo)}!")
    assert len(tdo) == 1
    conn.sendall(tdo)

from nmigen import Signal

def get_state_name(fsm, num):
    states = fsm.encoding
    rev = lambda xy: (xy[1],xy[0])
    mapping = dict(map(rev, states.items()))
    return mapping[num]


def get_sim_jtag_examine_passive(
    cpu: MtkCpu,
    jtag_fsm,
    timeout=10000,
):
    def f():
        yield Passive()
        addrs = []
        for i in range(20000):
        # for i in iter(int, 1):
        # while(True):
            state_num = yield jtag_fsm.state
            state_name = get_state_name(jtag_fsm, state_num)
            # if state_name != "TEST-LOGIC-RESET":
                # raise ValueError(f"state_name: .{state_name}.")
            addr = yield cpu.debug.dmi_address
            addrs.append(addr)
            if addr == 0x16:
                print(f"=== OK, dmi_addr eventually got value 0x16 (in {i} cycle).")
                return
            yield
        raise ValueError(f"Erorr: dmi_address never reached state 0x16! Addresses: {set(addrs)}")
    return f



def get_sim_jtag_controller(
    cpu: MtkCpu,
    timeout_cycles: int,
    jtag_fsm,
):

    if not cpu.with_debug:
        raise ValueError("CPU must be initialized with Debug Module present!")

    def jtag_controller(timeout=6000):
        yield Active()

        print("Waiting for OCD connection...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((HOST, PORT))
        s.listen()
        conn, addr = s.accept()
        print(f'OCD Connected! From addr: {addr}')

        jtag_loc = cpu.debug.jtag
        jtag_fsm_state = jtag_fsm.state
        cpu_tdi = jtag_loc.tdi
        cpu_tdo = jtag_loc.port.tdo
        cpu_tms = jtag_loc.tms
        cpu_tck = jtag_loc.tck

        CPU_JTAG_CLK_FACTOR = 5 # how many times JTAG clock is slower than CPU clock.

        DEBUGS = []

        prev_tck = None

        from termcolor import colored

        # cmd_gen = remote_jtag_get_cmd(conn)
        for i in range(timeout):
            cmd = AAA(conn)
            # cmd = next(cmd_gen)

            if isinstance(cmd, OcdCommand):
                # if i < 100:
                #     print(f"DEBUG: {cmd.value}")
                if cmd == OcdCommand.SAMPLE:
                    tdo = yield cpu_tdo
                    # DEBUGS.append(tdo)
                    # print(f"TDO: {tdo}")
                    remote_jtag_send_response(conn, bytes(str(tdo), 'ascii'))

                elif cmd == OcdCommand.RESET:
                    # MtkCpu doesn't support TRST signal for now.
                    for _ in range(5):
                        yield cpu_tms.eq(1)
                        for _ in range(CPU_JTAG_CLK_FACTOR):
                            yield

                    # print("RESET! TODO")
            elif isinstance(cmd, JTAGInput):
                if i < 100:
                    state_num = yield jtag_fsm_state
                    # print(f"DEBUG: {''.join(['  ' for _ in range(cmd.tms)])}{cmd.tms}, {jtag_get_state(state_num)}")
                yield cpu_tck.eq(cmd.tck)
                yield cpu_tms.eq(cmd.tms)
                # dummy = 1 - dummy
                # yield cpu_tms.eq(dummy)
                yield cpu_tdi.eq(cmd.tdi)
                DEBUGS.append((cmd.tms, cmd.tck))
                prev_tck = cmd.tck
                for _ in range(CPU_JTAG_CLK_FACTOR):
                    yield
            else:
                raise ValueError(f"Type mismatch! cmd must be either OcdCommand or JTAGInput, not {type(cmd)}!")
        
        def f(tms, tck):
            if tck == 0:
                return colored(str(tms), 'yellow')
            return str(tms)
        
        # print(", ".join([f(tms, tck) for (tms, tck) in DEBUGS]))

    return jtag_controller



def get_sel_bus_mask(sel):
    sel = format(sel, "04b")  # '1111' string for full mask
    return reduce(lambda val, el: (val << 8) + el, map(lambda x: 0xFF if int(x) == 1 else 0x00, sel))


def get_sim_memory_test(
    cpu: MtkCpu,
    mem_dict: Optional[MemoryContents],
):
    from nmigen.back.pysim import Passive

    def mem_test():
        yield Passive()
        # yield Tick()
        # yield Settle()
        p = 0.4  # .5 # probability of mem access in current cycle
        # TODO legacy - not used for now.
        # cursed - if we use state == MemState.FREE instead of list, 'timeout_range' generator wouldn't work.
        # param need to be passed by reference not by value, for actual binding to be visible in each loop iter.
        state = [MemState.FREE]

        arbiter = cpu.arbiter

        while True:  # that's ok, I'm passive.
            import numpy.random as random

            rdy = random.choice((0, 1), p=[1 - p, p])

            yield cpu.DEBUG_CTR

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
                    raise ValueError(
                        "ERROR (TODO handle): simultaneous 'read' and 'write' detected."
                    )
                if read:
                    state[0] = MemState.BUSY_READ
                elif write:
                    state[0] = MemState.BUSY_WRITE
                    data = yield arbiter.bus.dat_w
            else:
                if rdy:  # random indicated transaction done in current cycle
                    yield arbiter.bus.ack.eq(1)
                    sel = yield arbiter.bus.sel
                    mask = get_sel_bus_mask(sel)
                    read_val = mem_dict.get_default(mem_addr)
                    if state[0] == MemState.BUSY_WRITE:
                        mem_dict.set(
                            mem_addr, (read_val & ~mask) | (data & mask)
                        )
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
    check_mem = reg_num is not None

    def reg_test(timeout=default_timeout_extra + timeout_cycles):
        yield Active()
        yield Tick()
        yield Settle()

        for _ in range(timeout):
            en = yield cpu.reg_write_port.en
            if en == 1:
                addr = yield cpu.reg_write_port.addr
                if addr == reg_num:
                    val = yield cpu.reg_write_port.data
                    if check_mem and (val != expected_val):
                        # TODO that mechanism for now allows for only one write to reg, extend it if neccessary.
                        print(
                            f"== ERROR: Expected data write to reg x{addr} of value {expected_val},"
                            f" got value {val}.. \n== fail test: {name}\n"
                        )
                        print(
                            f"{format(expected_val, '32b')} vs {format(val, '32b')}"
                        )
                        exit(1)
                    return
            yield Tick()

        if check_mem:
            print(
                f"== ERROR: Test timeouted! No register write observed. Test: {name}\n"
            )
            exit(1)

    return reg_test
