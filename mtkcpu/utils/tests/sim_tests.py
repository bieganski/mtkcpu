from dataclasses import dataclass

import socket
from functools import reduce
from typing import Callable, Optional, Any
from enum import Enum
from amaranth.hdl.ast import Signal
from amaranth.sim import Active, Settle, Tick, Passive
from amaranth.hdl.ir import Elaboratable, Fragment


from mtkcpu.cpu.cpu import MtkCpu
from mtkcpu.utils.tests.memory import MemoryContents, MemState
from mtkcpu.units.debug.top import DMIReg
from mtkcpu.units.debug.impl_config import PROGBUF_MMIO_ADDR

def find_fsm(top, *path):
    assert isinstance(top, Elaboratable)
    # ugly hack for retrieving jtag FSM state for 'traces=vcd_traces' variable
    # https://freenode.irclog.whitequark.org/amaranth/2020-07-26#27592720;
    frag = Fragment.get(top, platform=None)
    fsm = frag.find_generated(*path) 
    # returned fsm instance has got attributes "state" (for current state signal) and "encoding" for state names mapping 
    return fsm

HOST = '127.0.0.1'
PORT = 9824


# XXX
# If  the  operation  didn’t  complete  in  time, 'op' will be 3 
# and the value in 'data' must be ignored.  
# The busy condition must be cleared by writing 'dmireset' in 'dtmcs', 
# and then the second scan scan must be performed again.




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

def rcv_cmd_from_gdb(conn):
    data = conn.recv(1)
    cmd = decode_cmd(data)
    return cmd


def remote_jtag_send_response(conn, tdo):
    if type(tdo) != bytes:
        raise ValueError(f"remote_jtag_send_response: 'tdo' must be bytes instance, not {type(tdo)}!")
    assert len(tdo) == 1
    conn.sendall(tdo)

def get_state_name(fsm, num):
    states = fsm.encoding
    rev = lambda xy: (xy[1],xy[0])
    mapping = dict(map(rev, states.items()))
    return mapping[num]


# sim threads communication via global variable
FINISH_SIM_OK = False

def get_sim_jtag_controller(cpu: MtkCpu):

    if not cpu.cpu_config.with_debug:
        raise ValueError("CPU must be initialized with Debug Module present!")

    def jtag_controller(timeout=15000):
        global FINISH_SIM_OK
        yield Active()

        from mtkcpu.utils.misc import get_color_logging_object
        logging = get_color_logging_object()

        logging.info("Waiting for OCD connection...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((HOST, PORT))
        s.listen()
        logging.info("Waiting for openOCD connection..")
        conn, addr = s.accept()
        logging.info(f'OCD Connected! From addr: {addr}')

        jtag_loc = cpu.debug.jtag
        cpu_tdi = jtag_loc.tdi
        cpu_tdo = jtag_loc.port.tdo
        cpu_tms = jtag_loc.tms
        cpu_tck = jtag_loc.tck

        CPU_JTAG_CLK_FACTOR = 4 # how many times JTAG clock is slower than CPU clock.

        def inf(i = 0):
            while(True):
                yield i
                i += 1
                if (i % 1000 == 0):
                    print(f"clk = {i}")                    
                if FINISH_SIM_OK:
                    print("== End Of Simulation Notification received, finishing with success..")
                    return # checkpoint checker catched all configurations
        timeout = None
        iter = inf() if not timeout else range(timeout)
        SETUP_CYCLES = 10
        for _ in range(SETUP_CYCLES):
            yield
        
        prev_tck = 0
        tck_ctr = 0
        
        for _ in iter:
            cmd = rcv_cmd_from_gdb(conn)

            if (tck_ctr and tck_ctr % 1000 == 0):
                print(f"                tck = {tck_ctr}")

            if isinstance(cmd, OcdCommand):
                if cmd == OcdCommand.SAMPLE:
                    tdo = yield cpu_tdo
                    remote_jtag_send_response(conn, bytes(str(tdo), 'ascii'))

                elif cmd == OcdCommand.RESET:
                    # MtkCpu doesn't support TRST signal for now.
                    for _ in range(5):
                        yield cpu_tms.eq(1)
                        for _ in range(CPU_JTAG_CLK_FACTOR):
                            yield

            elif isinstance(cmd, JTAGInput):
                yield cpu_tck.eq(cmd.tck)
                yield cpu_tms.eq(cmd.tms)
                yield cpu_tdi.eq(cmd.tdi)
                
                rising = cmd.tck > prev_tck
                if rising:
                    tck_ctr += 1
                prev_tck = cmd.tck
                
                for _ in range(CPU_JTAG_CLK_FACTOR):
                    yield
            else:
                raise ValueError(f"Type mismatch! cmd must be either OcdCommand or JTAGInput, not {type(cmd)}!")
        
    return jtag_controller



def get_sel_bus_mask(sel):
    sel = format(sel, "04b")  # '1111' string for full mask
    return reduce(lambda val, el: (val << 8) + el, map(lambda x: 0xFF if int(x) == 1 else 0x00, sel))


def get_sim_memory_test(
    cpu: MtkCpu,
    mem_dict: Optional[MemoryContents],
):
    def mem_test():
        yield Passive()
        # yield Tick()
        # yield Settle()
        p = 0.4  # .5 # probability of mem access in current cycle
        state = MemState.FREE

        arbiter = cpu.arbiter

        bus = arbiter.wb_bus

        while True:  # infinite loop is ok, I'm passive.
            import numpy.random as random

            rdy = random.choice((0, 1), p=[1 - p, p])

            if state == MemState.FREE:
                ack = yield bus.ack
                if ack:
                    yield bus.ack.eq(0)
                    yield
                    continue
                cyc = yield bus.cyc
                we = yield bus.we
                write = cyc and we
                read = cyc and not we
                mem_addr = yield bus.adr
                if read and write:
                    raise ValueError(
                        "ERROR (TODO handle): simultaneous 'read' and 'write' detected."
                    )
                if read:
                    state = MemState.BUSY_READ
                elif write:
                    state = MemState.BUSY_WRITE
                    data = yield bus.dat_w
                if mem_addr >= PROGBUF_MMIO_ADDR and mem_addr < PROGBUF_MMIO_ADDR + 0x20:
                    print(f"=== PROGBUF: putting {data} in {mem_addr}")
            else:
                # request processing
                if rdy:  # random indicated transaction done in current cycle
                    yield bus.ack.eq(1)
                    sel = yield bus.sel
                    mask = get_sel_bus_mask(sel)
                    read_val = mem_dict.get_default(mem_addr)
                    if state == MemState.BUSY_WRITE:
                        mem_dict.set(
                            mem_addr, (read_val & ~mask) | (data & mask)
                        )
                    elif state == MemState.BUSY_READ:
                        read_val &= mask
                        yield bus.dat_r.eq(read_val)
                        # print(f"==== fetched {read_val} (from {mem_dict})...")
                    state = MemState.FREE
            yield

    return mem_test


def get_sim_register_test(
    name: str,
    cpu: MtkCpu,
    timeout_cycles: int,
    reg_num: Optional[int],
    expected_val: Any,
    default_timeout_extra: int = 25,
):
    check_reg_content = reg_num is not None

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
                    if isinstance(expected_val, Callable):
                        cond = not expected_val(val)
                    else:
                        # anything that implements '=='
                        cond = val != expected_val
                    if check_reg_content and cond:
                        # TODO that mechanism for now allows for only one write to observed register per test,
                        # extend it if neccessary.
                        print(
                            f"== ERROR: Expected data write to reg x{addr} of value {hex(expected_val)},"
                            f" got value {hex(val)}.. \n== fail test: {name}\n"
                        )
                        print(
                            f"{format(expected_val, '32b')} vs {format(val, '32b')}"
                        )
                        exit(1)
                    return
            yield Tick()

        if check_reg_content:
            print(
                f"== ERROR: Test timeouted! No register write observed. Test: {name}\n"
            )
            exit(1)

    return reg_test
