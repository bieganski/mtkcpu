import socket
import sys
import select
from calc_gentest import gen_test

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

sfn = s.fileno()
ifn = sys.stdin.fileno()
p = select.poll()
p.register(sfn, select.POLLIN)
p.register(ifn, select.POLLIN)

tests = [
    ('#', 'ERR LEX'),
    ('2**2', 'ERR PARSE'),
    ('1/0', 'ERR DIVIDE'),
    ('2+2', '4'),
] + [gen_test() for _ in range(4096)]

fail = False

for i, (expr, val) in enumerate(tests):
    if i % 100 == 0:
        print(f'{i}/{len(tests)}...')
    data = (expr + '\n').encode()
    s.sendall(b'\x30' + len(data).to_bytes(4, 'little') + data)
    res = b''
    while b'\n' not in res:
        cmd = rxdm(1)
        if cmd == b'\xb1':
            sz = int.from_bytes(rxdm(2), 'little')
            d = rxdm(sz)
            res += d
        elif cmd == b'\xb2':
            n = int.from_bytes(rxdm(2), 'little')
            if n == 0x100:
                print(f'ARM UART RX OVERFLOW')
                sys.exit(1)
            elif n == 0x200:
                print(f'ARM UART FRAMING ERROR')
                sys.exit(1)
            elif n == 0x400:
                print(f'ARM UART PARITY ERROR')
                sys.exit(1)
            else:
                print(f'ARM UART ERROR {n:04x}')
                sys.exit(1)
        elif cmd == b'\x40':
            error()
        else:
            raise ValueError(cmd)
    i = res.index(b'\n')
    if i != len(res) - 1:
        print('ERR: more than one line received: ', res)
        sys.exit(1)
    res = res[:i].decode()
    if res != val:
        print(f'MISMATCH: expected {val} got {res}, test: {expr}')
        fail = True

if not fail:
    print('PASS')
