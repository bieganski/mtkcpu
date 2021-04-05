
![Alt text](svg/logo.png?raw=true "mtkCPU logo")

# mtkCPU

mtkCPU is as simple and as clear as possible implementation of RiscV ISA in [nMigen](https://github.com/nmigen/nmigen). There is one main file [cpu.py](./mtkcpu/cpu.py), that is including specific [units](./mtkcpu/units) (i.a. decoder, adder etc.)


### Running tests

```sh
pip3 install -r requirements.txt
python3 mtkcpu/test_cpu.py
```

### Unit tests structure

In general, all tests are done via `nmigen.back.pysim` backend. For best coverage and flexibility, you are able to **easily add your own tests, written in RiscV assembly**. For reference let's focus on simple test from `tests/reg_tests.py` file.

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

`WARNING` - unit test of that form possibilities are limited by compilator of `source` key used. For that we use `ppci`, which doesn't work well with branching/jumping instructions. For that reason, we decided to coverage branching with more compilcated [ELF tests](#elf-tests) 

### ELF tests

`mtkCPU` offers you with easy and seamless way of testing **your precompiled ELF file**. Just run

```sh
python3 mtkcpu/test_cpu.py --elf <ELF filepath>
```

To compile your code into RiscV assembly you can use `gcc` (install it via `install_toolchain.sh` script).
```sh
cd elf
./compile.sh example.S # it will generate example.elf using elf/linker.ld linker script.
```

Keep in mind, that CPU got hardcoded it's code address (with first instruction fetched). It's defined in `/mtkcpu/common.py` file at `START_ADDR` variable. You may want to use specially prepared linker script (or reuse example one, `/elf/linker.ld`, or change `common.py` file to adjust it for your precompiled ELF). 

`TODO` - for now we lack way of result verification, it may be something like `main` exit code. 


### Getting familiar

For quick dive into `mtkCPU` most painless way is to first run existing test (or add your own!) and look at important signals, reflecting control flow. For that purpose, I have prepared some `.gtkw` files, that opened in `gtkwave` util immediately will show you interesting signals. 

* `basic.gtkw` - First steps, good for beginners, without unit logic.
* `mem.gtkw` - For memory interface (however without memory arbiter).
* `full_mem.gtkw` - More advanced memory interface.


### About `nMigen`

`nMigen` is Python framework for digital design, it can compile either to netlist understandable by [yosys](https://github.com/YosysHQ/yosys) or `Verilog` code (that you can place and route using vendor tools, i.a. `Vivado`)

### nMigen docs/tutorials

* [Language guide](https://nmigen.info/nmigen/latest/lang.html)
* [Robert Baruch's introduction](https://github.com/RobertBaruch/nmigen-tutorial)
* [LambdaConcept's Step by Step](http://blog.lambdaconcept.com/doku.php?id=nmigen:tutorial)
* [Robert Baruch's refreshed RiscV playlist](https://www.youtube.com/playlist?list=PLEeZWGE3PwbZTypHq00G-yEX8TEI95lw4)


### Acknowledgements

Some parts of `mtkCPU` were inspired by [minerva CPU](https://github.com/lambdaconcept/minerva) parts (LambdaConcept's property).