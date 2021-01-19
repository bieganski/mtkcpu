DELTA = 0x9E3779B9

def enc(v, k):
    v0, v1 = v
    sum = 0
    for _ in range(32):
        sum += DELTA
        v0 += ((v1<<4) + k[0]) ^ (v1 + sum) ^ ((v1>>5) + k[1])
        v0 &= 0xffffffff
        v1 += ((v0<<4) + k[2]) ^ (v0 + sum) ^ ((v0>>5) + k[3])
        v1 &= 0xffffffff
    return [v0, v1]

def dec(v, k):
    v0, v1 = v
    sum = DELTA * 32
    for _ in range(32):
        v1 -= ((v0<<4) + k[2]) ^ (v0 + sum) ^ ((v0>>5) + k[3])
        v1 &= 0xffffffff
        v0 -= ((v1<<4) + k[0]) ^ (v1 + sum) ^ ((v1>>5) + k[1])
        v0 &= 0xffffffff
        sum -= DELTA
    return [v0, v1]

def xor(a, b):
    return [a[0] ^ b[0], a[1] ^ b[1]]

def crypt_sw(data, key, state, mode):
    assert len(data) % 2 == 0
    assert len(key) == 4
    assert len(state) == 2
    res = []
    for i in range(0, len(data), 2):
        src = data[i:i+2]
        if mode == 0:
            dst = enc(src, key)
        elif mode == 1:
            dst = dec(src, key)
        elif mode == 2:
            dst = state = enc(xor(src, state), key)
        elif mode == 3:
            dst = xor(dec(src, key), state)
            state = src
        elif mode == 4:
            dst = state = xor(src, enc(state, key))
        elif mode == 5:
            dst = xor(src, enc(state, key))
            state = src
        elif mode in (6, 7):
            dst = xor(src, enc(state, key))
            state = [state[0] + 1, state[1]]
        else:
            assert 0
        res += dst
    return res, state
