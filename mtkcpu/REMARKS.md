* No instruction-address-misaligned exception is generated for a conditional branch that is not taken.
* In particular, the sign bit for all immediates is always in bit 31 of the instruction to speed sign-extension circuitry.
* Immediate is always sign-extended to 32-bits before use in an arithmetic operation
* • The JALR instruction now clears the lowest bit of the calculated target address, to simplify
hardware and to allow auxiliary information to be stored in function pointers.

* Note that the JALR instruction does not treat the 12-bit immediate as multiples of 2 bytes,
unlike the conditional branch instructions. This avoids one more immediate format in hardware.
In practice, most uses of JALR will have either a zero immediate or be paired with a LUI or
AUIPC, so the slight reduction in range is not significant.
