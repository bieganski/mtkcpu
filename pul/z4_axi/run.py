import socket
import sys
import select
import random

from crypt_sw import crypt_sw

with open(sys.argv[1], 'rb') as f:
    bsd = f.read()

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect('/run/muxsrv.sock')

def rxdm(n):
    r = b''
    while len(r) < n:
        r += s.recv(n - len(r))
    return r

def error():
    l = int.from_bytes(rxdm(2), 'little')
    ds = rxdm(l).decode()

    print(f'ERROR: {ds}')
    sys.exit(1)

s.sendall(len(bsd).to_bytes(4, 'little') + bsd)

print('Wait for device')

c = rxdm(1)
if c == b'\x40':
    error()
elif c != b'\xa0':
    raise ValueError(c)
l = int.from_bytes(rxdm(2), 'little')
ds = rxdm(l).decode()

print(f'Device connected: {ds}')

c = rxdm(1)
if c == b'\x40':
    error()
elif c != b'\xa1':
    raise ValueError(c)

print('Device booted')

def wr32(addr, vals):
    s.sendall(b'\x12' + addr.to_bytes(4, 'little') + len(vals).to_bytes(4, 'little') + b''.join(v.to_bytes(4, 'little') for v in vals))
    c = rxdm(1)
    if c == b'\x40':
        error()
    elif c != b'\x92':
        raise ValueError(c)

def rd32(addr, num):
    s.sendall(b'\x02' + addr.to_bytes(4, 'little') + num.to_bytes(4, 'little'))
    c = rxdm(1)
    if c == b'\x40':
        error()
    elif c != b'\x82':
        raise ValueError(c)
    l = rxdm(4)
    if l != num.to_bytes(4, 'little'):
        raise ValueError(l)
    return [
        int.from_bytes(rxdm(4), 'little')
        for _ in range(num)
    ]

for i in range(1000):
    if i % 100 == 0:
        print(f'{i}/1000...')
    src_addr = 0x20000 | random.getrandbits(12) << 3
    dst_addr = 0x30000 | random.getrandbits(12) << 3
    count = random.getrandbits(10)
    mode = random.getrandbits(3)
    key = [
        random.getrandbits(32)
        for _ in range(4)
    ]
    state = [
        random.getrandbits(32)
        for _ in range(2)
    ]
    data = [
        random.getrandbits(32)
        for _ in range(count * 2)
    ]
    wr32(src_addr, data)
    wr32(dst_addr, [0xcccccccc for i in range(count * 2)])
    wr32(0x40000000, [*key, *state, src_addr, dst_addr, count, mode])

    # print('MODE', mode, count, hex(src_addr), hex(dst_addr))
    ctr = 0
    while True:
        status, = rd32(0x40000028, 1)
        # print('STATUS', status)
        if (status & 1) == 0:
            break
        ctr += 1
        if ctr >= count * 100 + 10:
            print('TIMEOUT WAITING FOR ~BUSY')
            sys.exit(1)

    if status & 2:
        print('GOT AXI ERROR')
        sys.exit(1)

    endstate = rd32(0x40000010, 2)
    out = rd32(dst_addr, count * 2)

    exp_out, exp_es = crypt_sw(data, key, state, mode)
    if exp_out != out or exp_es != endstate:
        print(f'FAILURE {mode} {key} {state} {data}')
        print(f'GOT {endstate} {out}')
        print(f'EXP {exp_es} {exp_out}')
        sys.exit(1)

print('PASS')
