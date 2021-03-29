# MEM_TESTS semantic:
# after executing t['source'], check whether in register xN (N = t['out_reg']) is value t['out_val'],
# providing that initial register state was: val(xN) = t['reg_init'][N] 
# and initial memory state: val(addr) = mem_init['addr'], check whether after executing t['source']
# in register xN (N = t['out_reg']) is value t['out_val'], and for all k, v in out_mem.items(): mem[k] == v.
# If t['out_val'] or t['out_mem'] is null, skip according check.


from bitstring import Bits

MEM_TESTS = [
    
    {
        "name": "simple 'lw'",
        "source": 
        """
        .section code
            addi x10, x0, 0xde
            lw x11, 0xde(x0)
        """,
        "out_reg": 11,
        "out_val": 0xdeadbeef,
        "timeout": 10,
        "mem_init": {0xde: 0xdeadbeef},
        "out_mem": {} # empty dict means whatever (no memory checks performed)
    },

    {
        "name": "simple 'sw'",
        "source": 
        """
        .section code
            sw x11, 0xaa(x0)
        """,
        "timeout": 10,
        "reg_init": [i for i in range(32)],
        "out_mem": {0xaa: 11}
    },

    {
        "name": "simple 'lh'",
        "source": 
        """
        .section code
            lh x5, 0xaa(x1)
        """,
        "timeout": 10,
        "out_reg": 5,
        "out_val": Bits(bin=format(0b11111111_11111111_11111111_00000000, '32b')).uint, # uint because of bus unsigned..
        "reg_init": [i for i in range(32)],
        "_mem_init": {0xab: 0b11011110_10101101_10111110_11101111}, # 0xdeadbeef
        "mem_init": {0xab: Bits(bin=format(0b11111111_00000000_11111111_00000000, '32b')).int},
    },

    {
        "name": "simple 'lhu'",
        "source": 
        """
        .section code
            lhu x5, 0(x0)
        """,
        "timeout": 10,
        "out_reg": 5,
        "out_val": 0b11111111_00000000,
        "mem_init": {0x0: Bits(bin=format(0b11111111_00000000_11111111_00000000, '32b')).int},
    },

    {
        "name": "simple 'lb'",
        "source": 
        """
        .section code
            lb x5, 0(x0)
        """,
        "timeout": 10,
        "out_reg": 5,
        "out_val": 0b11111101, # TODO fix that unsigned bus.
        "mem_init": {0x0: -3},
    },

    {
        "name": "simple 'lbu'",
        "source": 
        """
        .section code
            lbu x5, 0(x0)
        """,
        "timeout": 10,
        "out_reg": 5,
        "out_val": 5,
        "mem_init": {0x0: 5},
    },

    {
        "name": "simple 'sh'",
        "source": 
        """
        .section code
            sh x5, 0(x0)
        """,
        "timeout": 10,
        "reg_init": [i for i in range(32)],
        "mem_init": {0x0: 5},
        "mem_out": {0x0: 5}
    },

    {
        "name": "negative 'sh'",
        "source": 
        """
        .section code
            sh x5, 0(x0)
        """,
        "timeout": 10,
        "reg_init": [-5 for _ in range(32)],
        "mem_out": {0x0: Bits(bin=format(0b11111111_11111011, '32b')).uint},
    },

    {
        "name": "simple 'sb'",
        "source": 
        """
        .section code
            sb x5, 0(x1)
        """,
        "timeout": 10,
        "reg_init": [0xaa for _ in range(32)],
        "mem_out": {0xaa: 0xaa},
    },
]
