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

]