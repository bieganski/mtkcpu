#!/bin/bash


NUM=10
i=0
for i in `seq 1 $NUM`; do
	./bresenham_template.py simulate  | tee output.txt | grep -c PASS
done

echo "res: "
echo $i
