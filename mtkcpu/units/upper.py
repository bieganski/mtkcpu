from mtkcpu.utils.common import matcher
from mtkcpu.cpu.isa import InstrType

match_lui = matcher(
    [
        (InstrType.LUI,),
    ]
)

match_auipc = matcher(
    [
        (InstrType.AUIPC,),
    ]
)
