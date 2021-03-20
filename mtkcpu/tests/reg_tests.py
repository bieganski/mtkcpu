REG_TESTS = [

    ### ADD, SUB

    {  # 2 + 3 = 5
        "name": "simple 'add'",
        "source": 
        """
        .section code
            add x3, x2, x3
            lw t0, 0(t1)
            li t1, 0xdeadbeef
        """,
        "out_reg": 3,
        "out_val": 5,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [i for i in range(32)]
    },

    {  # 3 - 2 = 1
        "name": "simple 'sub'",
        "source": 
        """
        .section code
            sub x10, x3, x2
        """,
        "out_reg": 10,
        "out_val": 1,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [i for i in range(32)]
    },

    ### SRL, SRLI, SLL, SLLI

    {  # 0b111 >> 2 = 0b1 
        "name": "simple 'srli'",
        "source": 
        """
        .section code
            srli x10, x11, 2
        """,
        "out_reg": 10,
        "out_val": 0b1,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [0b111 for _ in range(32)]
    },

    {  # 0b1011 >> 1 = 0b101
        "name": "simple 'srl'",
        "source": 
        """
        .section code
            srl x10, x11, x1
        """,
        "out_reg": 10,
        "out_val": 0b101,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [i for i in range(32)]
    },

    {  # 0b111 << 2 = 0b11100 
        "name": "simple 'slli'",
        "source": 
        """
        .section code
            slli x10, x11, 2
        """,
        "out_reg": 10,
        "out_val": 0b11100,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [0b111 for _ in range(32)]
    },

    {  # 0b1011 << 1 = 0b10110
        "name": "simple 'sll'",
        "source": 
        """
        .section code
            sll x10, x11, x1
        """,
        "out_reg": 10,
        "out_val": 0b10110,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [i for i in range(32)]
    },

    ### SRA, SRAI

    {  # 0b1011 >> 1 = 0b101
        "name": "simple 'sra'",
        "source": 
        """
        .section code
            sra x10, x11, x1
        """,
        "out_reg": 10,
        "out_val": 0b101,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [i for i in range(32)]
    },

    {  # 0b111 >> 2 = 0b1 
        "name": "simple 'srai'",
        "source": 
        """
        .section code
            srai x10, x11, 2
        """,
        "out_reg": 10,
        "out_val": 0b1,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [0b111 for _ in range(32)]
    },

    {
        # calculated by https://www.cs.cornell.edu/courses/cs3410/2019sp/riscv/interpreter/
        "name": "fully functional 'srai'",
        "source": 
        """
        .section code
            srai x2, x1, 4
        """,
        "out_reg": 2,
        "out_val": -7 & 0xFFFFFFFF, # ah, that python infinite-bit representation...
        "timeout": 5,
        "mem_init": {},
        "reg_init": [-100 for _ in range(32)]
    },

    {  # same as above
        "name": "fully functional 'sra'",
        "source": 
        """
        .section code
            sra x2, x2, x1
        """,
        "out_reg": 2,
        "out_val": 0b11000000000000000000000000000000,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [0, 1, 0x80000000]
    },

    ### XOR, OR, AND

    {  # 0b00001 | 0b00111 = 0b111
        "name": "simple 'or'",
        "source": 
        f"""
        .section code
            or x2, x{0b00001}, x{0b00111}
        """,
        "out_reg": 2,
        "out_val": 0b111,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [i for i in range(32)]
    },
    
    {  # 0b10011 & 0b00111 = 0b11
        "name": "simple 'and'",
        "source": 
        f"""
        .section code
            and x2, x{0b10011}, x{0b00111}
        """,
        "out_reg": 2,
        "out_val": 0b11,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [i for i in range(32)]
    },

    {  # 0b10101 ^ 0b01111 = 0b11010
        "name": "simple 'xor'",
        "source": 
        f"""
        .section code
            xor x2, x{0b10101}, x{0b1111}
        """,
        "out_reg": 2,
        "out_val": 0b11010,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [i for i in range(32)]
    },

    ### XORI, ORI, ANDI 
    
    {  # 0b11111 ^ 0b01010 = 0b10101
        "name": "simple 'xori'",
        "source": 
        f"""
        .section code
            xori x5, x{0b11111}, {0b01010}
        """,
        "out_reg": 5,
        "out_val": 0b10101,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [i for i in range(32)]
    },

    {  # 0b00001 | 0b00111 = 0b111
        "name": "simple 'ori'",
        "source": 
        f"""
        .section code
            ori x2, x{0b00001}, {0b00111}
        """,
        "out_reg": 2,
        "out_val": 0b111,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [i for i in range(32)]
    },
    
    {  # 0b10011 & 0b00111 = 0b11
        "name": "simple 'andi'",
        "source": 
        f"""
        .section code
            andi x2, x{0b10011}, {0b00111}
        """,
        "out_reg": 2,
        "out_val": 0b11,
        "timeout": 5,
        "mem_init": {},
        "reg_init": [i for i in range(32)]
    },

]