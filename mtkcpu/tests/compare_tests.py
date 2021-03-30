CMP_TESTS = [
    
    {
        "name": "simple 'sltiu'",
        "source": 
        """
        .section code
            lui x1, 0xffff
            sltiu x2, x1, 0xffe
        """,
        "out_reg": 2,
        "out_val": 1,
        "timeout": 10,
    },

    {
        "name": "simple 'slti'",
        "source": 
        """
        .section code
            lui x1, 0xffff
            slti x3, x1, 0xffe
        """,
        "out_reg": 3,
        "out_val": 0,
        "timeout": 10,
    },

    {
        "name": "simple 'sltu'",
        "source": 
        """
        .section code
            sltu x1, x3, x2
        """,
        "out_reg": 1,
        "out_val": 1,
        "reg_init": [-i for i in range(32)],
        "timeout": 10,
    },

    {
        "name": "simple 'slt'",
        "source": 
        """
        .section code
            slt x1, x3, x2
        """,
        "out_reg": 1,
        "out_val": 1,
        "reg_init": [-i for i in range(32)],
        "timeout": 10,
    },

]