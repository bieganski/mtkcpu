#!/bin/bash

./module.py rtlil > res.il; yosys -p 'synth; show' res.il
