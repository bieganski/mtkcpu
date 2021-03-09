* No instruction-address-misaligned exception is generated for a conditional branch that is not taken.
* In particular, the sign bit for all immediates is always in bit 31 of the instruction to speed sign-extension circuitry.
* Immediate is always sign-extended to 32-bits before use in an arithmetic operation
* • The JALR instruction now clears the lowest bit of the calculated target address, to simplify
hardware and to allow auxiliary information to be stored in function pointers.
