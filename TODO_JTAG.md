https://riscv.org/wp-content/uploads/2017/05/Wed1445_Debug_WorkingGroup_Wachs.pdf

* Unimplemented instructions must select the BYPASS register.
* Variable "ROM" This is : jal x0 abstract, jal x0 program_buffer,
        //                or jal x0 resume, as desired.
        //                Debug Module state machine tracks what is 'desired'.
* A debugger can access memory from a hart’s point of view using a Program Buffer or the Abstract Access Memory command.
* RISC-V debug target that does not implement the program buffer, but instead implements the system bus access.
*  debug spec already specifies the size/presence of a Program Buffer in the dmstatus register. 
* rejestr abstracts (0x16) zawiera busy (1 if actually any abstract executed) oraz
	progbufsize (width 5, 0-16) in 32 bytes words

To halt, debugger:
1. Selects desired hart(s)
2. Sets DMCONTROL.haltreq
3. Waits for DMSTATUS.allhalted
4. Clears DMCONTROL.haltreq

To resume, debugger:
1. Selects desired hart(s)
2. Sets DMCONTROL.resumereq
3. Waits for DMSTATUS.allresumeack

IN DEBUG MODE:
* Interrupts are disabled
* Exceptions handled by debugger

Read/Write GPRs -- REQUIRED
•Read/Write CSRs -- Optional

To perform an abstract command:
1. Debugger writes argument(s) into DATA registers
2. Debugger writes COMMAND register
3. Debugger waits for ABSTRACTCS.busy = ǹ
4. Debugger reads results from DATA registers




PYTANIE:

== HARTINFO.dataccess

0: The data registers are shadowed in the hart
by CSRs. Each CSR is DXLEN bits in size, and
corresponds to a single argument, per Table 3.1.

1: The data registers are shadowed in the hart’s
memory map. Each register takes up 4 bytes in
the memory map.
