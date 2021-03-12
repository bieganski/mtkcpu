from enum import Enum

class Funct3(Enum):
    ADD = SUB = 0b000
    SLL = 0b001
    SLT = 0b010
    SLTU = 0b011
    XOR = 0b100
    SRL = 0b101
    SRA = 0b101
    OR = 0b110
    AND = 0b111

class Funct7(Enum):
    ADD = 0b0000000
    SUB = 0b0100000


class InstrType(Enum):
    LOAD = 0b00000
    STORE = 0b01000
    ADD = 0b10000
    SUB = 0b10001
    BRANCH = 0b11000
    JAL = 0b11001
    AUIPC = 0b00101
    LUI = 0b01101
    OP_IMM = 0b00100
    ALU = 0b0110011

class InstrFormat(Enum):
    R = 0 # addw t0, t1, t2
    I = 1 # addi t1, t0, 100
    S = 2 # sw t1, 8(t2)  # no destination register
    B = 3 # beq t1, t2, End # no destination register
    U = 4 # upper immediate - LUI, AUIPC  # Label: AUIPC x10, 0 # Puts address of label in x10 /* only imm20 and rd */
    J = 5
