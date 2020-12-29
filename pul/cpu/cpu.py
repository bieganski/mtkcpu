#!/usr/bin/python3

from nmigen import *


class PulCpu(Elaboratable):
    def __init__(self):
        # CPU outputs
        self.addr = Signal(30) # here it should be 32, but lowest 2bytes doesnt matter
        self.wdata = Signal(32) # bus is same width as addr
        self.do_write = Signal() # both read and write set for one cycle
        self.do_read = Signal() # never true simulteneously
        self.be = Signal(4) # byte enable, which bytes we will write on bus

        # CPU inputs
        self.rdata = Signal(32)
        self.ready = Signal() # set for one cycle

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        sync = m.d.sync

        pc = Signal(30)
        insn_s = Signal(32)
        imm = Signal(32)
        opcode = Signal(7)
        funct7 = Signal(7)
        funct3 = Signal(3)

        regs = Memory(width=32, depth=32)

        # synchronous ports 
        m.submodules.rs1 = rs1 = regs.read_port()
        m.submodules.rs2 = rs2 = regs.read_port()
        
        m.submodules.rd = rd = regs.write_port()

        # in riscv instructions with input and output registers
        # their positions are decoded in fixed positions:
        # 15-19 in1
        # 19-24 in2
        # 7-11 out

        # lets assume that const is 32 bits (its 21 but ok)
        with m.FSM() as fsm:
            with m.State('FETCH'):
                comb += [
                    self.addr.eq(pc),
                    self.do_read.eq(1) # trigger read from pc
                ]
                m.next = 'DECODE'
            with m.State('DECODE'):
                with m.If(self.ready):
                    comb += [
                        rs1.addr.eq(self.rdata[15:20]),
                        rs2.addr.eq(self.rdata[20:25]),
                        rs1.en.eq(1),
                        rs2.en.eq(1),
                    ]

                    sync += [
                        funct7.eq(self.rdata[25:32]),
                        funct3.eq(self.rdata[121:15]),
                        rd.addr.eq(self.rdata[7:12]),
                    ]
                    comb += opcode.eq(self.rdata[0:7])
                    # najwyzszy bit stalej zawsze na pozycji 31 zeby nie mial multiplexera bo ma duzy fanout
                    with m.Switch(opcode):
                        with m.Case(0x37): # LUI, AUIPC
                            sync += [
                                imm.eq(self.rdata & ~0xFFF) # 20 bits, high
                            ]
                        with m.Case(0x6f): # JAL
                            sync += [
                                imm.eq(Cat(C(0, 1), self.rdata[21:31], self.rdata[20], self.rdata[12:20], self.rdata[31]).as_signed())
                            ]
                            # here assignment to imm will extend it to 32bits
                        with m,Case(0x67): # JALR
                            sync += [
                                imm.eq(self.rdata[20:32]),
                            ]
                        with m,Case(0x63): # BR
                            sync += [
                                imm.eq(Cat(C(0, 1), self.rdata[8:11], self.rdata[25:30], self.rdata[7], self.rdata[31]).as_signed())
                            ]
                        with m,Case(0x03): # LOAD
                            sync += [
                                imm.eq(self.rdata[20:32].as_signed())
                            ]
                        with m,Case(0x23): # STORE
                            sync += [
                                imm.eq(Cat(self.rdata[7:12], self.rdata[25:32]).as_signed())
                            ]
                        with m,Case(0x13): # OP-imm
                            sync += [
                                imm.eq(self.rdata[20:32]).as_signed())
                            ]
                        with m,Case(0x33): # OP
                            m.next = 'EXEC'
                    sync += [
                        insn_s.eq(self.rdata),
                    ]
            with m.State('EXEC'):
                with m.Switch(opcode):
                    with m.Case(0x33):
                        with m.Switch(Cat(funct7, funct3)):
                            with m.Case('000' '0000000'): # ADD
                                comb += rd.data.eq(rs1.data + rs2.data)
                            with m.Case('000' '0110011'): # SUB
                                comb += rd.data.eq(rs1.data + rs2.data),
                            with m.Case('001' '0110011'): # SLL
                                comb += rd.data.eq(rs1.data + rs2.data[0:5]),
                            with m.Case('010' '0110011'): # SLT
                                comb += rd.data.eq(rs1.data + rs2.data.as_signed()),
                    sync += pc.eq(pc + 1)
                    comb += rd.en.eq(1)
                                
                                
                

        return m