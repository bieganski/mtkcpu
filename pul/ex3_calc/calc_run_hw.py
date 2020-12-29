import socket
import sys
import select

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

while True:
    for (fd, ev) in p.poll():
        if fd == sfn:
            cmd = rxdm(1)
            if cmd == b'\xb1':
                sz = int.from_bytes(rxdm(2), 'little')
                d = rxdm(sz)
                sys.stdout.write(d.decode())
            elif cmd == b'\xb2':
                n = int.from_bytes(rxdm(2), 'little')
                if n == 0x100:
                    print(f'ARM UART RX OVERFLOW')
                elif n == 0x200:
                    print(f'ARM UART FRAMING ERROR')
                elif n == 0x400:
                    print(f'ARM UART PARITY ERROR')
                else:
                    print(f'ARM UART ERROR {n:04x}')
            elif cmd == b'\x40':
                error()
            else:
                raise ValueError(cmd)
        elif fd == ifn:
            data = (input() + '\n').encode()
            s.sendall(b'\x30' + len(data).to_bytes(4, 'little') + data)
