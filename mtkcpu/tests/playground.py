PLAYGROUND_TESTS = [
    
    {
        "name": "YOUR PLAYGROUND TEST 1 (ppci)",
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
        "name": "YOUR PLAYGROUND TEST 2 (elf)",
        "elf": "tests/example.elf",
        "out_reg": 1,
        "out_val": 222,
        "timeout": 10,
    },

]