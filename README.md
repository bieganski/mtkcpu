# mtkCPU

### Brief

mtkCPU is as simple and as clear as possible implementation of RiscV ISA in [nMigen](https://github.com/nmigen/nmigen). There is one main file [cpu.py](./mtkcpu/cpu.py), that is including specific [units](./mtkcpu/units) (i.a. decoder, adder etc.)


### Tests

```sh
pip3 install -r requirements.txt
python3 mtkcpu/test_cpu.py
```
