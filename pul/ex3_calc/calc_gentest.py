import random

from calc_sw import calculate

def gen_subtree(d):
    while True:
        c = random.randrange(8 + d//2)
        if c == 0 or c >= 8 or d >= 128:
            val = random.getrandbits(32)
            res = str(val)
            prio = 0
        elif c == 1:
            s1, p1, v1 = gen_subtree(d + 1)
            res = '(' + s1 + ')'
            prio = 0
            val = v1
        elif c == 2:
            s1, p1, v1 = gen_subtree(d + 1)
            if p1 > 1:
                s1 = '(' + s1 + ')'
            res = '-' + s1
            prio = 1
            val = None if v1 is None else -v1
        elif c in {3, 4}:
            s1, p1, v1 = gen_subtree(d + 1)
            s2, p2, v2 = gen_subtree(d + 1)
            if p1 > 3:
                s1 = '(' + s1 + ')'
            if p2 > 2:
                s2 = '(' + s2 + ')'
            res = s1 + {3: '+', 4: '-'}[c] + s2
            prio = 3
            val = None if v1 is None or v2 is None else {3: v1+v2, 4: v1-v2}[c]
        else:
            s1, p1, v1 = gen_subtree(d + 1)
            s2, p2, v2 = gen_subtree(d + 1)
            if p1 > 2:
                s1 = '(' + s1 + ')'
            if p2 > 1:
                s2 = '(' + s2 + ')'
            res = s1 + {5: '*', 6: '/', 7: '%'}[c] + s2
            prio = 3
            if (v2 == 0 and c in {6, 7}) or v1 is None or v2 is None:
                val = None
            else:
                if c == 5:
                    val = v1 * v2
                elif c == 6:
                    val = v1 // v2
                elif c == 7:
                    val = v1 % v2
        if val is not None:
            val &= 0xffffffff
        if len(res) < 1024 and (val is not None or random.randrange(4) == 0):
            return res, prio, val
        # welp, retry


def gen_test():
    res = gen_subtree(0)
    if res[2] is None:
        return res[0], 'ERR DIVIDE'
    assert calculate(res[0]) == res[2]
    return res[0], str(res[2])


if __name__ == '__main__':
    for _ in range(256):
        print(*gen_test())
