#!/usr/bin/env python3

import socket

HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 9824        # Port to listen on (non-privileged ports are > 1023)


from enum import Enum


    # B - Blink on
	# b - Blink off
	# R - Read request
	# Q - Quit request
	# 0 - Write 0 0 0
	# 1 - Write 0 0 1
	# 2 - Write 0 1 0
	# 3 - Write 0 1 1
	# 4 - Write 1 0 0
	# 5 - Write 1 0 1
	# 6 - Write 1 1 0
	# 7 - Write 1 1 1
	# r - Reset 0 0
	# s - Reset 0 1
	# t - Reset 1 0
	# u - Reset 1 1
class OcdCommand(Enum):
    SAMPLE = b'R'
    QUIT = b'Q'
    BLINK_ON = b"B"
    BLINK_OFF = b"b"
    RESET = b"r"
    # RESET = 

    # @classmethod
    def skip(self):
        return self.value in [OcdCommand.BLINK_ON.value, OcdCommand.BLINK_OFF.value]

# TODO
# after https://www.python.org/dev/peps/pep-0622/
# unify JTAGInput and OcdCommand.
class JTAGInput():
    def __init__(self, ocd_bitbang_val):
        self.tck = int(ocd_bitbang_val & 0x4 != 0)
        self.tms = int(ocd_bitbang_val & 0x2 != 0)
        self.tdi = int(ocd_bitbang_val & 0x1 != 0)
    
    def __repr__(self):
        return f"TCK: {self.tck}, TMS: {self.tms}, TDI: {self.tdi}"

    def tms():
        return self.tms

    def tdi():
        return self.tdi

    def tck():
        return self.tck

    # cursed
    def skip(self):
        return False

def decode_cmd(char):
    # from openocd/.../remote_bitbang.c
    # char c = '0' + ((tck ? 0x4 : 0x0) | (tms ? 0x2 : 0x0) | (tdi ? 0x1 : 0x0));
    if ord(char) < ord('8') and ord(char) >= ord('0'):
        return JTAGInput(ord(char) - ord('0'))
    return OcdCommand(char)
        

def remote_jtag_get_instr():


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    conn, addr = s.accept()
    with conn:
        print('Connected by', addr)
        while True:
            data = conn.recv(1)
            print(f"data: {data}")
            if not data:
                break
            cmd = decode_cmd(data)
            print(cmd)
            if cmd.skip():
                continue
            conn.sendall(b"0")
            # conn.sendall(b"\0")
            # conn.sendall(b"\0")
    print("koniec")

if __name__ == "__main__":
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        conn, addr = s.accept()
