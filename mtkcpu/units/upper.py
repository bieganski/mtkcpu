from mtkcpu.utils.common import matcher
from mtkcpu.utils.isa import Funct3, InstrType

match_lui = matcher([
    (InstrType.LUI, ),
])

match_auipc = matcher([
    (InstrType.AUIPC, ),
])