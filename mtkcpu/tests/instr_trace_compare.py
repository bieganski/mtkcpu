# NOTICE

# that file is (slightly modified) copy that comes from google/riscv-dv repository
# https://github.com/google/riscv-dv/blob/master/scripts/riscv_trace_csv.py.
# delete that copy when moving riscv-dv to submodule. 



"""
Copyright 2019 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Compare the instruction trace CSV
"""

import re
import sys
from typing import List


from riscv_trace_csv import *


def compare_trace_csv(csv1, csv2, name1, name2, log):
    if log:
        fd = open(log, 'a+')
    else:
        fd = sys.stdout

    fd.write("{} : {}\n".format(name1, csv1))
    fd.write("{} : {}\n".format(name2, csv2))

    with open(csv1, "r") as fd1, open(csv2, "r") as fd2:
        instr_trace_1 : List[RiscvInstructionTraceEntry] = []
        instr_trace_2 : List[RiscvInstructionTraceEntry]= []
        
        trace_csv_1 = RiscvInstructionTraceCsv(fd1)
        trace_csv_2 = RiscvInstructionTraceCsv(fd2)
        trace_csv_1.read_trace(instr_trace_1)
        trace_csv_2.read_trace(instr_trace_2)
        
        print(f"len {name1}: {len(instr_trace_1)}")
        print(f"len {name2}: {len(instr_trace_2)}")
        
        gpr_state_1 = {}
        gpr_state_2 = {}

        for i, (entry1, entry2) in enumerate(zip(instr_trace_1, instr_trace_2)):
            reg_write_1 = check_update_gpr(entry1.gpr, gpr_state_1)
            reg_write_2 = check_update_gpr(entry2.gpr, gpr_state_2)
            debug_msg = f"line {i + 1}: {(entry1, entry2)}"
            if not reg_write_1:
                assert not reg_write_2, debug_msg
                continue
            assert reg_write_1 and reg_write_2, debug_msg

            def parse_gpr(gpr_str : str):
                rd, val = gpr_str.split(":")
                return (reg_abi_name_to_phys(rd), int(val, 16))

            regs1 = sorted([parse_gpr(x) for x in entry1.gpr])
            regs2 = sorted([parse_gpr(x) for x in entry2.gpr])
            
            assert len(regs1) == len(regs2) == 1 # we don't use that fact for now

            for (rd1, val1), (rd2, val2) in zip(regs1, regs2):
                assert rd1 == rd2, f"{rd1} != {rd2}, {debug_msg}"
                if val1 != val2:
                    raise ValueError(f"{i}: Detect value mismatch: {hex(val1)} vs {hex(val2)}. {debug_msg} {gpr_state_1} , {gpr_state_2}")
                # else:
                #     print(f"{i}: OK, value {hex(val1)} written to {rd1} in both cases!")
            
        print(f"OK, got {min(len(instr_trace_1), len(instr_trace_2))} matches!")

def reg_abi_name_to_phys(abi_name: str):
    matches = re.findall(r'\d+', abi_name)
    if len(matches) > 1:
        raise ValueError(f"reg_abi_name_to_phys: abi_name: {abi_name}, matches: {matches}")
    
    num = int(matches[0]) if len(matches) == 1 else None
    
    if abi_name.startswith("x"):
        return abi_name
    if abi_name.startswith("a"):
        return f"x{num + 10}"
    if abi_name == "zero":
        return "x0"
    if abi_name == "ra":
        return "x1"
    if abi_name == "sp":
        return "x2"
    if abi_name == "gp":
        return "x3"
    if abi_name == "tp":
        return "x4"
    if abi_name == "fp" or abi_name == "s0":
        return "x8"
    if abi_name == "s1":
        return "x9"
    if abi_name.startswith("t"):
        assert num is not None, (abi_name, matches)
        if num <= 2:
            return f"x{num + 5}"
        elif 3 <= num <= 6:
            return f"x{num + 25}"  
    if abi_name.startswith("s"):
        assert num is not None, (abi_name, matches)
        return f"x{num + 16}"
    assert False, abi_name

def check_update_gpr(gpr_update, gpr_global_state):
    gpr = gpr_global_state
    gpr_state_change = 0
    for update in gpr_update:
        if update == "":
            return 0
        item = update.split(":")
        if len(item) != 2:
            sys.exit("Illegal GPR update format:" + update)
        rd = reg_abi_name_to_phys(item[0])
        rd_val = item[1]
        if rd in gpr:
            if rd_val != gpr[rd]:
                gpr_state_change = 1
        else:
            if int(rd_val, 16) != 0:
                gpr_state_change = 1
        gpr[rd] = rd_val
    return gpr_state_change
