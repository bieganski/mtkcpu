def parametrized(dec):
    def layer(*args, **kwargs):
        def repl(f):
            return dec(f, *args, **kwargs)
        return repl
    return layer


def rename(new_name: str):
    def decorator(f):
        f.__name__ = new_name
        return f
    return decorator
