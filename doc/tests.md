# Testing

In general, all `mtkCPU` simulation tests are via `amaranth.back.pysim` backend. 

## Unit tests

For best coverage and flexibility, you are able to **easily add your own tests, written in RiscV assembly**. For reference let's focus on simple test from [tests/test_registers.py](../mtkcpu/tests/test_registers.py) file.

```python
REG_TESTS = [
   ...
    MemTestCase(
        name="simple 'sub'",
        source_type=MemTestSourceType.TEXT,
        source="""
        .section code
            sub x10, x3, x2
        """,
        out_reg=10,
        out_val=1,
        timeout=5,
        mem_init=MemoryContents.empty(), # empty {each valid memory address holds 0x0}
        reg_init=RegistryContents.fill(), # fill: { x_i := i }, e.g. x5 initially will hold value 5.
    ),
]
```

The testbench does nothing but captures all writes to register file, and when first write to `out_reg` is detected, it compares written value to specified by `out_val` parameter, throwing error in case of mismatch.

Note that such test structure is very convenient: For instance, let's consider test below, that tests the branch instructions:

```python
    MemTestCase(
        name="jump taken 'bne'",
        source_type=MemTestSourceType.RAW,
        source="""
            start:
                bne x1, x0, jump_taken
                addi x1, x0, 111
            jump_taken:
                addi x1, x0, 222
        """,
        out_reg=1,
        reg_init=RegistryContents.fill(),
        out_val=222,
        timeout=10,
    ),
```

Remember, that simulation finishes when **first** write to `x1` is captured. To test `branch not taken` condition, the only change would be `out_val=111` instead of `out_val=222`.  



## `riscv-dv` tests

More advanced, randomized tests are provided using [`riscv-dv`](https://github.com/google/riscv-dv) framework. Using UVM libraries and a capable simulator (e.g. QuestaSim), `riscv-dv` generates few-kilobytes-big .elf files filled with random instructions. As a next step it invokes ISS (e.g. Spike), with some verbose-trace flag (e.g. Spike must be compiled with `--enable-commitlog` and invoked with `--log-commits`), which on each executed instruction prints CPU registers state. Such log is in `.csv` format, and it's responsibility of your testbench to print the log in same format. Resulting two logs are further compared (each line should match between those two).

`mtkCPU` currently supports two `riscv-dv` tests:
* `riscv_arithmetic_basic_test`
* `riscv_arithmetic_rand_testriscv_u_mode_rand_test`

The first one checks arithmetic instructions and the second virtual memory accesses (it setup's page tables, writes to `satp` CSR and `mret`'s to `User` mode).

Testbench for `riscv-dv` is located [here](../mtkcpu/tests/test_riscv_dv.py).

As a result of simulation following `.csv` is created:

```
pc,instr,gpr,csr,binary,mode,instr_str,operand,pad
80000000,,t0:00000000,,f14022f3,3,"csrr    t0, mhartid",,
80000004,,t1:00000000,,00000313,3,"li      t1, 0",,
8000000c,,a3:8000000c,,00000697,3,"auipc   a3, 0x0",,
80000010,,a3:80000018,,00c68693,3,"addi    a3, a3, 12",,
80000018,,a4:40000000,,40000737,3,"lui     a4, 0x40000",,
8000001c,,a4:40000100,,10070713,3,"addi    a4, a4, 256",,
80000024,,t4:80016024,,00016e97,3,"auipc   t4, 0x16",,
...
```

After each instruction that writes to `rd` it's simulator job to print content of `rd` in format
`rd:value_after_execution`, e.g. `a4:40000000` after `lui a4, 0x40000`.



## `openOCD + GDB` tests

`mtkCPU` has implemented Debug Module (with regards to [Debug spec](https://riscv.org/wp-content/uploads/2019/03/riscv-debug-release.pdf)), compatible with default openOCD implementation.

`openOCD` can operate with different transport protocols, for board connection it uses e.g. `ftdi`, but for simulations useful is `remote_bitbang`. It sends values of JTAG input signals (`TCK`, `TMS`, `TDI`) via TCP, and in the same connection it waits for `TDO` value.

Looking at the `openOCD` [source code](https://openocd.org/doc/doxygen/html/remote__bitbang_8c_source.html) we see how the values are serialized:

```c
static int remote_bitbang_write(int tck, int tms, int tdi)
 {
     char c = '0' + ((tck ? 0x4 : 0x0) | (tms ? 0x2 : 0x0) | (tdi ? 0x1 : 0x0));
     return remote_bitbang_queue(c, NO_FLUSH);
 }
 ```

 `mtkCPU` testbench implements following pseudocode:

 ```python

conn = bind(localhost, 9000) # openOCD is on the other side

while true:
    input_serialized = conn.recv()
    tck, tms, tdi = deserialize(input_serialized)

    # drive cpu signals
    yield cpu.jtag.tck.eq(tck)
    yield cpu.jtag.tms.eq(tms)
    yield cpu.jtag.tms.eq(tdi)

    tdo = yield cpu.jtag.tdo # retrieve value from the simulator state

    conn.send(tdo)

    yield Tick()
 ```

To make everything work, the [JTAG testbench](../mtkcpu/utils/tests/utils.py) does the following:
1) runs `gdb` (`riscv-none-elf-gdb`), passing an example .elf
2) runs the `openOCD`, makes connection with `gdb`
3) GDB parses .elf and sends it content to `openOCD` via internal protocol
4) `openOCD` translates it to JTAG instructions, there are passeed to simulator via TCP channel
5) simulator drives specific signals and returns feedback to `openOCD`