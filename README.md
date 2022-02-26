
![Alt text](svg/logo.png?raw=true "mtkCPU logo")

# mtkCPU

mtkCPU is as simple and as clear as possible implementation of RiscV ISA in [Amaranth HDL](https://github.com/amaranth-hdl/amaranth). There is one main file [cpu.py](mtkcpu/cpu/cpu.py), that is including specific [units](./mtkcpu/units) (i.a. decoder, adder etc.)


### Features
* implements basic ISA `rv32i`
* `Machine` mode and `User` mode
* traps and interrupts
* CSR registers support
* optional Virtual Memory System - allows for memory translation in `User` mode
* Debug Module - can connect openOCD and GDB, compatible with [Risc-V Debug Spec](https://riscv.org/wp-content/uploads/2019/03/riscv-debug-release.pdf)
* bsp (board specific files) generation - based on RTL code it generates proper `.h` and `.cc` files

### Supported hardware
The design was tested on [`ice40`](https://www.latticesemi.com/iCE40) FPGA on the [`iCEBreaker`](https://1bitsquared.com/products/icebreaker) board.


### Quick Start
See [Quick Start Page](doc/run.md) and find out how simple it is to deploy fully functional `mtkCPU` with one command!
We provide one-liner that generates a bitstream with Block RAM memory initialized with a specified .elf's content!


### Test coverage
* pure-assembly unit tests (more than 80 tests present, each instruction covered)
* single-block testbenches
* co-simulation with `openOCD` and `GDB` testing Debug Module
* randomized tests (arithmetic and MMU) using [riscv-dv](https://github.com/google/riscv-dv) framework from Google


### Running simulation tests

```sh
pip3 install .
pytest -x -n4 mtkcpu/tests/
```

For more information about how tests work, please refer to [that file](./doc/tests.md).

### About `Amaranth HDL` (previously `nMigen`)

`Amaranth HDL` is a Python framework for digital design, it can compile either to netlist understandable by [yosys](https://github.com/YosysHQ/yosys) or `Verilog` code (that you can place and route using vendor tools, e.g. `Vivado`)

### Amaranth HDL docs/tutorials

* [Language guide](https://amaranth-lang.org/docs/amaranth/latest/)
* [Robert Baruch's introduction](https://github.com/RobertBaruch/nmigen-tutorial)
* [LambdaConcept's Step by Step](http://blog.lambdaconcept.com/doku.php?id=nmigen:tutorial)
* [Robert Baruch's refreshed RiscV playlist](https://www.youtube.com/playlist?list=PLEeZWGE3PwbZTypHq00G-yEX8TEI95lw4)


### Acknowledgements

Some parts of `mtkCPU` were inspired by [minerva CPU](https://github.com/lambdaconcept/minerva) parts (LambdaConcept's property).
