
![Alt text](svg/logo.png?raw=true "mtkCPU logo")

# mtkCPU

`mtkCPU` is a **simple, clear, hackable and very inefficient** implementation of RiscV ISA in [Amaranth HDL](https://github.com/amaranth-hdl/amaranth). There is one main file [cpu.py](mtkcpu/cpu/cpu.py), that is including specific [units](./mtkcpu/units) (i.a. decoder, adder etc.)


### Features
* implements basic ISA `rv32i`
* `Machine` mode and `User` mode
* traps and interrupts
* bsp (board specific files) generation - based on RTL code it generates proper `.h` and `.cc` files
* CSR registers support
* Virtual Memory System - allows for memory translation in `User` mode
* **Debug Module - connect GDB to the CPU!**

### Debug Module?
Debug Module (DM) is a part of a CPU that exposes things like CPU registers, or memory bus via JTAG interface, so that one can **control the running CPU from the host PC**.


**The DM implementation is compatible with [RISC-V Debug Specs 1.0](https://raw.githubusercontent.com/riscv/riscv-debug-spec/master/riscv-debug-stable.pdf)**, which means that you can use mainstream `openOCD` and `GDB` and it will Just Work™. 

**NOTE:** There are more serious future plans going for `DM` implementation - we are going to move it to a separate repository and form as a **plugin that can be used with any other CPU implementation**. Read more about future plans [here](doc/future.md).

### Supported hardware
The design was tested on [`ice40`](https://www.latticesemi.com/iCE40) FPGA on the [`iCEBreaker`](https://1bitsquared.com/products/icebreaker) board.


### Quick Start
See [Quick Start Page](doc/run.md) and find out how simple it is to deploy fully functional `mtkCPU` with one command!
We provide one-liner that generates a bitstream with Block RAM memory initialized with a specified .elf's content!


### And.. what if I want to try it with openOCD and GDB?

[Watch the GDB Demo on YouTube!](https://www.youtube.com/watch?v=Erod5Yj1vxA)

So the [Quick start](#quick-start) is really quick to start with, but it "embeds" program embedded in bitstream and loaded during board programming. In order to change the program, full bitstream 
rebuild is required. 

Due to the fact, that `mtkcpu` implements `Debug Module`, we may load the program using GDB+openOCD. Changing program that is running is possible during runtime, without bitstream reprogramming. Also, **you have full GDB debugging capabilities, like breakpoints and single-stepping**. See [openOCD+GDB Quick Start guide](./doc/gdb.md) for more details.


### Contributing

mtkCPU is under active and keen development, and you are invited to become part of it! Just make sure first to read [the contribution page](./doc/contrib.md).

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


### License, acknowledgements

`mtkCPU` is licensed under GPLv2 terms. Some parts of `mtkCPU` come from [minerva CPU](https://github.com/lambdaconcept/minerva) (LambdaConcept's property, released under [license](doc/MINERVA_LICENSE.txt)).

