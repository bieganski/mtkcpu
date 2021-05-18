from enum import Enum

class Funct3(Enum):
    ADD = SUB = ADDI = B = JALR = BEQ = 0b000
    SLL = SLLI = H = BNE = 0b001
    SLTU = 0b011
    SLT = SLTI = W = 0b010
    XOR = BU = BLT = 0b100
    SRL = SRLI = HU = BGE = 0b101
    SRA = SRAI  = 0b101
    OR = BLTU = 0b110
    AND = BGEU = 0b111

class Funct7(Enum):
    ADD = SRL = SLL = SRLI = SLLI = 0b0000000
    SUB = SRA = SRAI = 0b0100000


class InstrType(Enum):
    BRANCH  = 0b1100011
    JAL     = 0b1101111
    JALR    = 0b1100111
    AUIPC   = 0b0010111
    LUI     = 0b0110111
    OP_IMM  = 0b0010011
    ALU     = 0b0110011
    LOAD    = 0b0000011
    STORE   = 0b0100011

class InstrFormat(Enum):
    R = 0 # addw t0, t1, t2
    I = 1 # addi t1, t0, 100
    S = 2 # sw t1, 8(t2)  # no destination register
    B = 3 # beq t1, t2, End # no destination register
    U = 4 # upper immediate - LUI, AUIPC  # Label: AUIPC x10, 0 # Puts address of label in x10 /* only imm20 and rd */
