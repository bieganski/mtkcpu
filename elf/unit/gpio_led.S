
.global start


.text

start:
	li x1, 0x80000000 # GPIO base address
	li x2, 0b11
	li x3, 1 # const
store:
	xor x2, x2, x3
	sb x2, 0(x1)
	li x4, 1000000
loop:
	addi x4, x4, -1
	bne x4, x0, loop
	jal x0, store
