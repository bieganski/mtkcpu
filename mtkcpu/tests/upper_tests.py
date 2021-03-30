from bitstring import Bits
from common import START_ADDR

UPPER_TESTS = [
    
    {
        "name": "simple 'lui'",
        "source": 
        """
        .section code
            lui x1, 0xfffff
        """,
        "out_reg": 1,
        "out_val": Bits(uint=0xfffff000, length=32).uint,
        "timeout": 10,
    },

    {
        "name": "overwrite 'lui'",
        "source": 
        """
        .section code
            lui x1, 0xfffff
        """,
        "out_reg": 1,
        "out_val": Bits(uint=0xfffff0aa, length=32).uint,
        "reg_init": [0xaa for _ in range(32)],
        "timeout": 10,
    },

    {
        "name": "simple 'auipc'",
        "source": 
        """
        .section code
            auipc x1, 0xaa
        """,
        "out_reg": 1,
        "out_val": START_ADDR + (0xaa << 12),
        "timeout": 10,
    },
]