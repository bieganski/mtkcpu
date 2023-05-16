from typing import Sequence, Callable
import logging

from mtkcpu.utils.misc import get_color_logging_object

logging = get_color_logging_object() # XXX
# logging.setLevel(XXX)

class LazyEvalBool:
    """
    XXX that is a wrapper on a 'bool', 
    but provides a third variant "unknown", a param-less callable to be computed. 
    when calculating logical expression 
    containing LazyEvalBool, the result is an instance of LazyEvalBool as well, 
    and the "unknown" value propagates. 
    """
    TRUE = True
    FALSE = False
    UNKNOWN = None
    
    def __init__(self, value):
        if isinstance(value, Callable):
            self.value = value
        # XXX below is damn dangerous, as we operate on references...
        # elif isinstance(value, LazyEvalBool):
        #     self.value = value.value
        elif isinstance(value, bool):
            self.value = value
        else:
            raise TypeError(f"{type(value)} is not a valid argument type")
    
    @property
    def computed(self):
        return isinstance(self.value, bool)
    
    @property
    def computable(self):
        assert not self.computed
        return isinstance(self.value, Callable)
    
    def try_compute(self) -> bool:
        """
        Returns True iff the computation was done and the result was stored.
        """
        assert self.computable
        f = self.value
        assert isinstance(f, Callable)
        val = f()
        assert isinstance(val, LazyEvalBool)
        if val.computed:
            # self.value is written only if invocation returned non UNKNOWN value.
            self.value = val.value
            return True
        return False
    
    def __bool__(self):
        if not self.computed:
            raise ValueError("Cannot convert TristateBool with value 'unknown' to bool")
        return self.value
    
    def __and__(self, other):
        if isinstance(other, bool):
            return self.__and__(LazyEvalBool(other))
        assert isinstance(other, LazyEvalBool)
        if not (self.computed and other.computed):
            return LazyEvalBool(LazyEvalBool.UNKNOWN)
        return LazyEvalBool(self.value and other.value)
    
    def __or__(self, other):
        if isinstance(other, bool):
            return self.__or__(LazyEvalBool(other))
        assert isinstance(other, LazyEvalBool)
        if not (self.computed and other.computed):
            return LazyEvalBool(LazyEvalBool.UNKNOWN)
        return LazyEvalBool(self.value or other.value)
    
    def __invert__(self):
        if not self.computed:
            return LazyEvalBool(LazyEvalBool.UNKNOWN)
        return LazyEvalBool(not self.value)
    
    def __repr__(self):
        if not self.computed:
            if self.computable:
                return "TristateBool.LAMBDA"
            return "TristateBool.UNKNOWN"
        return f"TristateBool({self.value})"

def evaluate_conditions_inplace(values: Sequence[LazyEvalBool]) -> None:
    while True:
        for x in values:
            logging.info(f"{x} is computed - {x.computed}")
            
            if (not x.computed) and x.computable:
                have_result = x.try_compute()
                if have_result: 
                    logging.info(f"successfully computed {x.value}")
                    break
        else:
            # loop computed nothing - time for summary.
            if all([x.computed for x in values]):
                return values
            raise ValueError("condition_evaluator: Detected an unsolvable loop!")


# XXX move it to some unit test.
a = LazyEvalBool(True)
b = LazyEvalBool(lambda : a)
c = LazyEvalBool(lambda : a or b)
# lst = [(x if isinstance(x, LazyEvalBool) else LazyEvalBool(x)) for x in [a,b,c]]
lst = [a, b, c]
assert all(evaluate_conditions_inplace(lst))
print("=========================================================")
a.value = False
assert all(evaluate_conditions_inplace(lst[1:])) # XXX such use case not supported, not sure if it's needed.
