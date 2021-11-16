
.global start


.text

start:
	beq x0, x0, jump_taken
	addi x1, x0, 111
jump_taken:
	addi x1, x0, 222
