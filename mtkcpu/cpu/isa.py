from enum import Enum, unique


class Funct3(int, Enum):
    ADD = SUB = ADDI = B = JALR = BEQ = PRIV = 0b000
    SLL = SLLI = H = BNE = CSRRW = 0b001
    SLTU = CSRRC = 0b011
    SLT = SLTI = W = CSRRS = 0b010
    XOR = BU = BLT = 0b100
    SRL = SRLI = HU = BGE = CSRRWI = 0b101
    SRA = SRAI = 0b101
    OR = BLTU = CSRRSI = 0b110
    AND = BGEU = CSRRCI = 0b111


class Funct7(int, Enum):
    ADD = SRL = SLL = SRLI = SLLI = 0b0000000
    SUB = SRA = SRAI = 0b0100000
    MRET = 0b011000


class Funct12(int, Enum):
    ECALL = 0b000000000000
    EBREAK = 0b000000000001
    WFI = 0b000100000101
    MRET = 0b001100000010


@unique
class InstrType(int, Enum):
    BRANCH = 0b1100011
    JAL = 0b1101111
    JALR = 0b1100111
    AUIPC = 0b0010111
    LUI = 0b0110111
    OP_IMM = 0b0010011
    ALU = 0b0110011
    LOAD = 0b0000011
    STORE = 0b0100011
    SYSTEM = 0b1110011 # TODO check two last bits


@unique
class InstrFormat(int, Enum):
    REGISTER = 0  # addw t0, t1, t2
    IMMEDIATE = 1  # addi t1, t0, 100
    STORE = 2  # sw t1, 8(t2)  # no destination register
    BRANCH = 3  # beq t1, t2, End # no destination register
    UPPER_IMMEDIATE = 4  # upper immediate - LUI, AUIPC
    # Label: AUIPC x10, 0 # Puts address of label in x10 /* only imm20 and rd */
