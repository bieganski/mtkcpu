
### Unit tests structure

In general, all tests are done via `amaranth.back.pysim` backend. For best coverage and flexibility, you are able to **easily add your own tests, written in RiscV assembly**. For reference let's focus on simple test from `tests/reg_tests.py` file.

```python
REG_TESTS = [
   ...
{  # 3 - 2 = 1
        "name": "simple 'sub'",
        "source": 
        """
        .section code
            sub x10, x3, x2
        """,
        "out_reg": 10,
        "out_val": 1,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [i for i in range(32)]
},
]
```

Example above represents entire test. Simulator executes code passed as `source` key. Before test, CPU registers are initialized with `reg_init` values (`assert len(reg_init) <= 32; x_i == reg_init[i] # or 0 if i >= len(reg_init)`). During simulation, it captures all writes to register file, and in case of write to `out_reg` it compares written value to `out_val`, throwing error in case of mismatch.

Simulation also contains latency-randomized memory interconnect (simplified Wishbone protocol), thus you are able to tests operations like `load` or `store` (as coveraged in `tests/mem_tests.py`).
For memory testing, put dict of `address, value (4 byte)` at `mem_init` key, and dict of constraints (of same form), that will be checked **after** simulation ends (after `timeout` cycles).


`NOTE` - unit test of that form possibilities are limited by compilator of `source` key used. For that we use `ppci`, which doesn't work well with branching/jumping instructions. For that reason, we decided to coverage branching with stable RiscV compiler `riscv-none-embed-gcc`. It's usage is straightforward: put your code as same way as you did in `source` key, but now in `source_raw` key. Whole content will be copied to temporary `.S` file and compiled to ELF format, then run same way that you would run simulation of whole ELF (like [here](#elf-tests)) 

