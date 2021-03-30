from bitstring import Bits

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
]