#!/usr/bin/env python3

from cpu import MtkCpu
from tests.reg_tests import REG_TESTS
from tests.mem_tests import MEM_TESTS
from tests.compare_tests import CMP_TESTS
from tests.upper_tests import UPPER_TESTS
from tests.branch_tests import BRANCH_TESTS

from argparse import ArgumentParser

parser = ArgumentParser(description="mtkCPU testing script.")
parser.add_argument('--reg', action='store_const', const=REG_TESTS, default=[], required=False)
parser.add_argument('--mem', action='store_const', const=MEM_TESTS, default=[], required=False)
parser.add_argument('--cmp', action='store_const', const=CMP_TESTS, default=[], required=False)
parser.add_argument('--upper', action='store_const', const=UPPER_TESTS, default=[], required=False)
parser.add_argument('--branch', action='store_const', const=BRANCH_TESTS, default=[], required=False)
parser.add_argument('--verbose', action='store_const', const=True, default=False, required=False)

parser.add_argument('--elf', metavar='<ELF file path.>', type=str, required=False, help="Simulate given ELF binary.")

args = parser.parse_args()

ELF = "../elf/example.elf" # TODO use 'args.elf' instead

from asm_dump import chunks


# returns memory (for now only .text section) as dictionary.
def read_elf(elf_path, verbose=False):
    from elftools.elf.elffile import ELFFile
    elf = ELFFile(open(elf_path, 'rb'))
    
    import subprocess
    p = subprocess.Popen(["riscv-none-embed-objdump", "--disassembler-options=no-aliases",  "-M",  "numeric", "-d", ELF], stdout=subprocess.PIPE)
    out, _ = p.communicate()

    out = str(out.decode("ascii"))
    if verbose:
        print(out)
    
    from asm_dump import bytes_to_u32_arr, dump_instrs
    raw = elf.get_section_by_name(".text").data()
    code = bytes_to_u32_arr(raw)
    if verbose:
        dump_instrs(code)
    exit(1)

# read_elf(ELF, True)

ALL_TESTS = REG_TESTS + MEM_TESTS + CMP_TESTS + UPPER_TESTS
SELECTED_TESTS = args.mem + args.reg + args.cmp + args.upper + args.branch if args.branch + args.upper + args.cmp + args.mem + args.reg != [] else ALL_TESTS
VERBOSE = args.verbose


# checks performed: 
# * if 'expected_val' is not None: check if x<'reg_num'> == 'expected_val',
# * if 'expected_mem' is not None: check if for all k, v in 'expected_mem.items()' mem[k] == v.
def reg_test(name, asm_str, timeout_cycles, reg_num, expected_val, expected_mem, reg_init, mem_init, verbose=False):
    from io import StringIO
    source_file = StringIO(asm_str)
    from asm_dump import dump_asm
    from nmigen.back.pysim import Simulator, Active, Passive, Tick, Settle

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

    assert((reg_num is None and expected_val is None) or (reg_num is not None and expected_val is not None))
    check_reg = reg_num is not None
    check_mem = expected_mem is not None

    def TEST_MEM():
        yield Passive()
        # yield Tick()
        # yield Settle()
        p = .4 # .5 # probability of mem access in current cycle
        from enum import Enum
        class MemState(Enum):
            FREE = 0
            BUSY_READ = 1
            BUSY_WRITE = 2

        # TODO legacy - not used for now.
        # cursed - if we use state == MemState.FREE instead of list, 'timeout_range' geneartor wouldn't work.
        # param need to be passed by reference not by value, for actual binding to be visible in each loop iter.
        state = [MemState.FREE]

        arbiter = cpu.arbiter

        while(True): # that's ok, I'm passive.
            import numpy.random as random

            rdy = random.choice((0, 1), p=[1-p, p])

            ctr = yield cpu.DEBUG_CTR

            if state[0] == MemState.FREE:
                ack = yield arbiter.bus.ack
                if ack:
                    yield arbiter.bus.ack.eq(0)
                    # print(f"DEBUG_CTR: {ctr}, state: {state[0]}")
                    yield
                    continue
                cyc = yield arbiter.bus.cyc
                we  = yield arbiter.bus.we
                write = cyc and     we 
                read  = cyc and not we
                mem_addr = yield arbiter.bus.adr
                if read and write:
                    raise ValueError("ERROR (TODO handle): simultaneous 'read' and 'write' detected.")
                if read:
                    state[0] = MemState.BUSY_READ
                elif write:
                    state[0] = MemState.BUSY_WRITE
                    data = yield arbiter.bus.dat_w
            else:
                if rdy: # random indicated transaction done in current cycle
                    yield arbiter.bus.ack.eq(1)
                    sel = yield arbiter.bus.sel
                    sel = format(sel, '04b') # '1111' string for full mask
                    f = lambda x : 0xFF if int(x) == 1 else 0x00
                    g = lambda val, el: (val << 8) + el
                    from functools import reduce
                    mask = reduce(g, map(f, sel))
                    read_val = 0x0 if mem_addr not in mem_dict else mem_dict[mem_addr]
                    if state[0] == MemState.BUSY_WRITE:
                        print(f"XXXX: GOT WRITE! val: {data}, addr: {mem_addr}, mask: {format(mask, '032b')}")
                        mem_dict[mem_addr] = (read_val & ~mask) | (data & mask)
                    elif state[0] == MemState.BUSY_READ:
                        read_val &= mask
                        yield arbiter.bus.dat_r.eq(read_val)
                        print(f"cyc {ctr}: fetched {read_val} (from {mem_dict})...")
                    state[0] = MemState.FREE
            yield
        

    def TEST_REG(timeout=35):
        yield Active()
        yield Tick()
        yield Settle()

        for _ in range(timeout):
            en = yield cpu.reg_write_port.en
            if en == 1:
                addr = yield cpu.reg_write_port.addr
                if addr == reg_num:
                    val = yield cpu.reg_write_port.data
                    if check_reg and (val != expected_val):
                        # TODO that mechanism for now allows for only one write to reg, extend it if neccessary.
                        print(f"== ERROR: Expected data write to reg x{addr} of value {expected_val}," 
                        f" got value {val}.. \n== fail test: {name}\n")
                        print(f"{format(expected_val, '32b')} vs {format(val, '32b')}")
                        exit(1)
                    return
            yield Tick()
        
        if check_reg:
            print(f"== ERROR: Test timeouted! No register write observed. Test: {name}\n")
            exit(1)
    
    sim.add_sync_process(TEST_MEM)
    sim.add_sync_process(TEST_REG)
    with sim.write_vcd("cpu.vcd"):
        sim.run()

    if check_mem:
        print(">>> MEM CHECKING: exp. vs val:", expected_mem, mem_dict)
        for k, v in expected_mem.items():
            if not k in mem_dict:
                print(f"Error! Wrong memory state. Expected {v} value in {k} addr, got nothing here!")
                exit(1)
            if mem_dict[k] != v:
                print(f"Error! Wrong memory state. Expected {v} value in {k} addr, got {mem_dict[k]}")
                exit(1)
    


if __name__ == "__main__":
    print("===== Running tests...")
    for i, t in enumerate(SELECTED_TESTS, 1):
        name     = t['name']     if 'name'     in t else f"unnamed: \n{t['source']}\n"
        reg_init = t['reg_init'] if 'reg_init' in t else [0 for _ in range(32)]
        mem_init = t['mem_init'] if 'mem_init' in t else {}
        out_reg  = t['out_reg']  if 'out_reg'  in t else None
        out_val  = t['out_val']  if 'out_val'  in t else None
        mem_out  = t['mem_out']  if 'mem_out'  in t else None
        reg_test(
            name=name, 
            asm_str=t['source'], 
            timeout_cycles=t['timeout'], 
            reg_num=out_reg, 
            expected_val=out_val, 
            expected_mem=mem_out, 
            reg_init=reg_init,
            mem_init=mem_init,
            verbose=VERBOSE)
        print(f"== Test {i}/{len(SELECTED_TESTS)}: <{name}> completed successfully..")

    # from minized import MinizedPlatform, TopWrapper
    # m = MtkCpu(32)
    # MinizedPlatform().build(TopWrapper(m), do_program=False)
