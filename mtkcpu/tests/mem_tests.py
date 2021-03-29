# MEM_TESTS semantic:
# after executing t['source'], check whether in register xN (N = t['out_reg']) is value t['out_val'],
# providing that initial register state was: val(xN) = t['reg_init'][N] 
# and initial memory state: val(addr) = mem_init['addr'], check whether after executing t['source']
# in register xN (N = t['out_reg']) is value t['out_val'], and for all k, v in out_mem.items(): mem[k] == v.
# If t['out_val'] or t['out_mem'] is null, skip according check.

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
]