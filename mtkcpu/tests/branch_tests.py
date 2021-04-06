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
        "name": "jump taken 'jalr'",
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
        "name": "jump taken backward 'jalr'",
        "source": 
        """
        .section code
            jalr x10, x0, 12
            addi x5, x0, 10
            addi x5, x0, 20
            jalr x10, x0, -4
        """,
        "out_reg": 5,
        "out_val": 20,
        "timeout": 20,
    },

# NOTE:
# ppci got problems with compiling 'jal' and branching instructions, thus compile it and test ELF
# (note we use 'source_raw' instead of 'source').
    
    {
        "name": "rd write 'jal'",
        "source_raw": 
        """
            start:
                jal x10, 0x0
        """,
        "out_reg": 10,
        "out_val": START_ADDR + 4,
        "timeout": 10,
    },

    {
        "name": "jump taken 'jal'",
        "source_raw": 
        """
            start:
                jal x10, jump_taken
                addi x1, x0, 111
            jump_taken:
                addi x1, x0, 222
        """,
        "out_reg": 1,
        "out_val": 222,
        "timeout": 10,
    },

    {
        "name": "jump taken backward 'jal'",
        "source_raw": 
        """
            jump_taken:
                addi x1, x0, 222
            start:
                jal x10, jump_taken
                addi x1, x0, 111
        """,
        "out_reg": 1,
        "out_val": 222,
        "timeout": 10,
    },

    {
        "name": "jump taken 'beq'",
        "source_raw": 
        """
            start:
                beq x1, x0, jump_taken
                addi x1, x0, 111
            jump_taken:
                addi x1, x0, 222
        """,
        "out_reg": 1,
        "reg_init": [0 for i in range(32)],
        "out_val": 222,
        "timeout": 10,
    },

    {
        "name": "jump not taken 'beq'",
        "source_raw": 
        """
            start:
                beq x1, x0, jump_taken
                addi x1, x0, 111
            jump_taken:
                addi x1, x0, 222
        """,
        "out_reg": 1,
        "reg_init": [i for i in range(32)],
        "out_val": 111,
        "timeout": 10,
    },

    {
        "name": "jump taken 'bne'",
        "source_raw": 
        """
            start:
                bne x1, x0, jump_taken
                addi x1, x0, 111
            jump_taken:
                addi x1, x0, 222
        """,
        "out_reg": 1,
        "reg_init": [i for i in range(32)],
        "out_val": 222,
        "timeout": 10,
    },

    {
        "name": "jump not taken 'bne'",
        "source_raw": 
        """
            start:
                bne x1, x0, jump_taken
                addi x1, x0, 111
            jump_taken:
                addi x1, x0, 222
        """,
        "out_reg": 1,
        "reg_init": [0 for i in range(32)],
        "out_val": 111,
        "timeout": 10,
    },

    {
        "name": "jump taken 'blt'",
        "source_raw": 
        """
            start:
                blt x0, x1, jump_taken
                addi x10, x0, 111
            jump_taken:
                addi x10, x0, 222
        """,
        "out_reg": 10,
        "reg_init": [i for i in range(32)],
        "out_val": 222,
        "timeout": 10,
    },

    {
        "name": "jump not taken 'blt'",
        "source_raw": 
        """
            start:
                blt x1, x0, jump_taken
                addi x10, x0, 111
            jump_taken:
                addi x10, x0, 222
        """,
        "out_reg": 10,
        "reg_init": [i for i in range(32)],
        "out_val": 111,
        "timeout": 10,
    },

    {
        "name": "jump taken 'bltu'",
        "source_raw": 
        """
            start:
                bltu x0, x1, jump_taken
                addi x10, x0, 111
            jump_taken:
                addi x10, x0, 222
        """,
        "out_reg": 10,
        "reg_init": [-i for i in range(32)],
        "out_val": 222,
        "timeout": 10,
    },

    {
        "name": "jump not taken 'bltu'",
        "source_raw": 
        """
            start:
                bltu x1, x0, jump_taken
                addi x10, x0, 111
            jump_taken:
                addi x10, x0, 222
        """,
        "out_reg": 10,
        "reg_init": [-i for i in range(32)],
        "out_val": 111,
        "timeout": 10,
    },

    {
        "name": "jump taken 'bge'",
        "source_raw": 
        """
            start:
                bge x1, x0, jump_taken
                addi x10, x0, 111
            jump_taken:
                addi x10, x0, 222
        """,
        "out_reg": 10,
        "reg_init": [i for i in range(32)],
        "out_val": 222,
        "timeout": 10,
    },

    {
        "name": "jump not taken 'bge'",
        "source_raw": 
        """
            start:
                bge x1, x0, jump_taken
                addi x10, x0, 111
            jump_taken:
                addi x10, x0, 222
        """,
        "out_reg": 10,
        "reg_init": [-i for i in range(32)],
        "out_val": 111,
        "timeout": 10,
    },

    {
        "name": "jump taken 'bgeu'",
        "source_raw": 
        """
            start:
                bgeu x1, x0, jump_taken
                addi x10, x0, 111
            jump_taken:
                addi x10, x0, 222
        """,
        "out_reg": 10,
        "reg_init": [-i for i in range(32)],
        "out_val": 222,
        "timeout": 10,
    },

    {
        "name": "jump not taken 'bgeu'",
        "source_raw": 
        """
            start:
                bgeu x0, x1, jump_taken
                addi x10, x0, 111
            jump_taken:
                addi x10, x0, 222
        """,
        "out_reg": 10,
        "reg_init": [-i for i in range(32)],
        "out_val": 111,
        "timeout": 10,
    },
]