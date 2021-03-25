# mtkCPU

mtkCPU is as simple and as clear as possible implementation of RiscV ISA in [nMigen](https://github.com/nmigen/nmigen). There is one main file [cpu.py](./mtkcpu/cpu.py), that is including specific [units](./mtkcpu/units) (i.a. decoder, adder etc.)


### Tests

```sh
pip3 install -r requirements.txt
python3 mtkcpu/test_cpu.py
```

### About `nMigen`

`nMigen` is Python framework for digital design, it can compile either to netlist (understandable by [yosys](https://github.com/YosysHQ/yosys)) or `Verilog` code (that you can place and route using vendor tools, i.a. `Vivado`)

### nMigen docs/tutorials

* [Language guide](https://nmigen.info/nmigen/latest/lang.html)
* [Robert Baruch's introduction](https://github.com/RobertBaruch/nmigen-tutorial)
* [LambdaConcept's Step by Step](http://blog.lambdaconcept.com/doku.php?id=nmigen:tutorial)
* [Robert Baruch's refreshed RiscV playlist](https://www.youtube.com/playlist?list=PLEeZWGE3PwbZTypHq00G-yEX8TEI95lw4)
