from common import START_ADDR

BRANCH_TESTS = [
    {
        "name": "rd write 'jalr'",
        "source": 
        """
        .section code
            jalr x10, x0, 0
        """,
        "out_reg": 10,
        "out_val": START_ADDR + 4,
        "timeout": 10,
    },

    {
        "name": "check jump taken 'jalr'",
        "source": 
        """
        .section code
            jalr x10, x0, 8
            addi x5, x0, 10
            addi x5, x0, 20
        """,
        "out_reg": 5,
        "out_val": 20,
        "timeout": 10,
    },

    {
        "name": "rd write 'jal'",
        "source": 
        """
        .section code
            jal x10, 0x0
        """,
        "out_reg": 10,
        "out_val": START_ADDR + 4,
        "timeout": 10,
    },
]