REG_TESTS = [
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
        "mem_init": [],
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
        "mem_init": [],
        "reg_init": [i for i in range(32)]
    },

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
        "mem_init": [],
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
        "mem_init": [],
        "reg_init": [i for i in range(32)]
    },
]
[

    {  # 2r + 222i = 224
        "name": "simple inplace 'addi'",
        "source": 
        """
        .section code
            addi x2, x2, 111
        """,
        "out_reg": 2,
        "out_val": 224,
        "timeout": 5,
        "mem_init": [],
        "reg_init": [i for i in range(32)]
    },

]