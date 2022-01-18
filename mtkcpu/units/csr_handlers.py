from typing import Dict
import logging

from amaranth import Signal, Module
from amaranth.hdl.rec import Record

from mtkcpu.cpu.priv_isa import *
from mtkcpu.utils.common import CODE_START_ADDR

class RegisterResetValue:
    def __init__(self, layout) -> None:
        self.layout = layout
        self.sanity_check()

    def field_values(self) -> Dict[str, int]:
        raise NotImplementedError("ReadOnlyRegValue must implement 'field_values(self)' method!")

    def __len__(self):
        return sum([x[1] for x in self.layout])

    def set_reset(self, rec : Record):
        fields : Dict[str, int] = self.field_values()
        for name, sig in rec.fields.items():
            if isinstance(sig, Signal):
                reset_val = fields.get(name, None)
                if reset_val is None:
                    logging.info(f"set_reset: could not find signal with name '{name}' among {fields.keys()}. Default value (0) will be used")
                else:
                    logging.info(f"setting reset val {hex(reset_val)} to signal {name}")
                    sig.reset = reset_val
            elif isinstance(sig, Record):
                assert False
                self.set_reset(sig)
            else:
                assert False
    
    @property
    def value(self) -> int:
        fields = self.field_values()
        res, off = 0, 0
        for name, width, *_ in self.layout:
            res |= fields.get(name, 0) << off # zero initialize
            off += width
        return res

    @property
    def layout_field_names(self):
        return [name for name, *_  in self.layout]

    def sanity_check(self):
        for name in self.field_values().keys():
            if name not in self.layout_field_names:
                raise ValueError(f"name {name} does not match known from layout {self.layout}")
        
class RegisterCSR():
    def __init__(self, csr_idx, layout, reset_value_t):
        self.name = self.__class__.__name__.lower()
        self._reset_value : RegisterResetValue = reset_value_t(layout)
        bits = len(self._reset_value)
        assert bits == 32
        self.rec = Record(__class__.reg_make_rw(layout))
        self._reset_value.set_reset(self.rec.r)
        self.csr_idx = csr_idx
        self.controller = None
        self.csr_unit = None

    @staticmethod
    def reg_make_rw(layout):
        f = lambda x : x[:2]
        return [
            ("r", list(map(f, layout))),
            ("w", list(map(f, layout))),
        ]

    @property
    def reset_value(self):
        return self._reset_value.value
    
    def associate_with_csr_unit(self, controller : "ControllerInterface", csr_unit : "CsrUnit"):
        self.controller = controller
        self.csr_unit = csr_unit

    def get_m(self) -> Module:
        csr_unit = self.csr_unit
        if csr_unit is None:
            raise ValueError("RegisterCSR: self.csr_unit not set during elaboration! Did you call super().__init__()?")
        return self.csr_unit.m
    
    def handler_notify_comb(self):
        m = self.get_m()
        m.d.comb += self.controller.handler_done.eq(1)

    def handle_write(self):
        raise NotImplementedError("RegisterCSR must implement 'handle_write(self)' method!")


class ReadOnlyRegisterCSR(RegisterCSR):
    # user doesn't have way to change it's read value.
    def handle_write(self):
        self.handler_notify_comb()

class WriteOnlyRegisterCSR(RegisterCSR):
    # only user is able to affect it's read value.
    pass

class MISA(ReadOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {
                "mxl": MisaRXL.RV32,
                "extensions": MisaExtensionBit.INTEGER_BASE_ISA,
            }
    def __init__(self):
        super().__init__(CSRIndex.MISA, misa_layout, __class__.RegValueLocal)


# TODO make me WriteOnlyRegisterCSR
class MTVEC(RegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {
                "mode": MtvecModeBits.DIRECT,
                "base": (CODE_START_ADDR + 0x20) >> 2
            }
    def __init__(self):
        super().__init__(CSRIndex.MTVEC, mtvec_layout, __class__.RegValueLocal)

    def handle_write(self):
        m = self.get_m()
        m.d.sync += [
            self.rec.r.base.eq(self.csr_unit.rs1val >> 2)
        ]
        self.handler_notify_comb()

class MTVAL(ReadOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRIndex.MTVAL, flat_layout, __class__.RegValueLocal)

class MEPC(ReadOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRIndex.MEPC, flat_layout, __class__.RegValueLocal)

# TODO make it WriteOnlyRegisterCSR
class MSCRATCH(RegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRIndex.MSCRATCH, flat_layout, __class__.RegValueLocal)

    def handle_write(self):
        m = self.get_m()
        m.d.sync += [
            self.rec.r.value.eq(self.csr_unit.rs1val)
        ]
        self.handler_notify_comb()

class MHARTID(ReadOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRIndex.MHARTID, flat_layout, __class__.RegValueLocal)

class MCAUSE(ReadOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRIndex.MCAUSE, mcause_layout, __class__.RegValueLocal)

class MTIME(ReadOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRNonStandardIndex.MTIME, flat_layout, __class__.RegValueLocal)


class MTIMECMP(WriteOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRNonStandardIndex.MTIMECMP, flat_layout, __class__.RegValueLocal)

    def handle_write(self):
        m = self.get_m()
        # From https://forums.sifive.com/t/how-to-clear-interrupt-in-interrupt-handler/2781:
        # The timer interrupt for example is cleared with writing a new value to the mtimecmp register (which must be higher than the current timer value).
        m.d.sync += [
            self.csr_unit.mip.mtip.eq(0)
        ]
        self.handler_notify_comb()


class MSTATUS(RegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRIndex.MSTATUS, mstatus_layout, __class__.RegValueLocal)

    def handle_write(self):
        m = self.get_m()
        m.d.sync += [
            self.rec.r.eq(self.rec.w) # TODO dangerous (doesn't implement WARL) - change it
        ]
        self.handler_notify_comb()

class MIE(WriteOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRIndex.MIE, mie_layout, __class__.RegValueLocal)

    def handle_write(self):
        m = self.get_m()
        # TODO
        self.handler_notify_comb()

# TODO
# For now it's fully readonly - doesn't support software interrupts,
# normally triggered via write to {m|s|u}sip field.
class MIP(ReadOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRIndex.MIP, mip_layout, __class__.RegValueLocal)
