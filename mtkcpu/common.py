from operator import or_
from functools import reduce
from itertools import starmap


# https://github.com/lambdaconcept/minerva/blob/master/minerva/units/decoder.py
def matcher(encodings):
    return lambda opcode, funct3, funct7: reduce(or_, 
        starmap(
            lambda opc, f3=None, f7=None:
                (opcode == opc if opc is not None else 1) \
                & (funct3 == f3 if f3 is not None else 1) \
                & (funct7 == f7 if f7 is not None else 1)
            ,
            encodings
        )
    )