
.global start


.text

start:
	beq x1, x2, jump_taken
	addi x1, x0, 111
jump_taken:
	addi x1, x0, 222
