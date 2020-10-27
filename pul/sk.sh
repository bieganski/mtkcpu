#!/bin/bash

# DOT viewer
./counter.py rtlil > res.il
yosys -p 'proc; synth; run' res.il
yosys -p 'proc; synth; dump' res.il
yosys -p 'proc; synth; show' res.il

# python add.py > tst.il && yosys tst.il -p 'synth_xilinx -noiopad -family xc7; splitnets; show'
