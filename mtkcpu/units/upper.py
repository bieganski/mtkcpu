from common import matcher
from isa import Funct3, InstrType

match_lui = matcher([
    (InstrType.LUI, ),
])

match_auipc = matcher([
    (InstrType.AUIPC, ),
])