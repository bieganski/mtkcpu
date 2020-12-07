#!/usr/bin/env python3

class CalcError(Exception):
    pass


class LexerError(CalcError):
    pass


class ParserError(CalcError):
    pass


class DivideError(CalcError):
    pass


def tokenize(line):
    # tokens are:
    # - int
    # - characters: ()+-*/%
    # - 'E' representing end of input
    is_num = False
    num = 0
    for x in line:
        if x in '+-*/%()':
            if is_num:
                yield num & 0xffffffff
                is_num = False
            yield x
        elif x in ' \t':
            if is_num:
                yield num & 0xffffffff
                is_num = False
        elif x in '0123456789':
            if not is_num:
                is_num = True
                num = 0
            num *= 10
            num += int(x)
        else:
            raise LexerError()
    if is_num:
        yield num & 0xffffffff
    yield 'E'


def calculate(line):
    # stack can contain:
    # - ints
    # - open parantheses: '('
    # - binary operators: '+', '-', '*', '/', '%'
    # - unary minus operator: 'U'
    stack = []
    for token in tokenize(line):
        # a minus is unary if it doesn't follow a number (possibly obtained by previous reduction)
        if token == '-':
            if not stack or not isinstance(stack[-1], int):
                token = 'U'

        # if followed by +-), reduce +-
        if token in list('+-)E'):
            while len(stack) >= 3 and isinstance(stack[-1], int) and stack[-2] in list('+-') and isinstance(stack[-3], int):
                b = stack.pop()
                op = stack.pop()
                a = stack.pop()
                if op == '+':
                    stack.append(a + b & 0xffffffff)
                elif op == '-':
                    stack.append(a - b & 0xffffffff)
                else:
                    assert 0

        if token == ')':
            # for ), pop the matching (
            if len(stack) >= 2 and isinstance(stack[-1], int) and stack[-2] == '(':
                num = stack.pop()
                stack.pop()
                stack.append(num)
            else:
                raise ParserError()
        elif token == 'E':
            if len(stack) == 1 and isinstance(stack[0], int):
                return stack[0]
            else:
                raise ParserError()
        else:
            # otherwise, just push the token on stack
            stack.append(token)

        # reduce unary minus if possible
        while len(stack) >= 2 and isinstance(stack[-1], int) and stack[-2] == 'U':
            num = stack.pop()
            stack.pop()
            stack.append(-num & 0xffffffff)

        # reduce */% if possible
        while len(stack) >= 3 and isinstance(stack[-1], int) and stack[-2] in list('*/%') and isinstance(stack[-3], int):
            b = stack.pop()
            op = stack.pop()
            a = stack.pop()
            if op == '*':
                stack.append(a * b & 0xffffffff)
            elif op == '/':
                if b == 0:
                    raise DivideError()
                stack.append(a // b)
            elif op == '%':
                if b == 0:
                    raise DivideError()
                stack.append(a % b)
            else:
                assert 0

    # should not reach here — 'E' is recognized above
    assert 0

print(calculate('13 * 2'))
