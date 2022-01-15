from typing import Dict
import logging

from amaranth import Signal, Module
from amaranth.hdl.rec import Record

from mtkcpu.cpu.priv_isa import *
from mtkcpu.utils.common import CODE_START_ADDR

class RegisterResetValue:
    excluded_from_init = ["zero"]

    def __init__(self, layout) -> None:
        self.layout = layout
        self.sanity_check()

    def field_values(self) -> Dict[str, int]:
        raise NotImplementedError("ReadOnlyRegValue must implement 'field_values(self)' method!")

    def __len__(self):
        return sum([x[1] for x in self.layout])

    def set_reset(self, rec : Record):
        defined_fields : Dict[str, int] = self.field_values()
        for name, sig in rec.fields.items():
            if isinstance(sig, Signal):
                reset_val = defined_fields.get(name, None)
                if reset_val is None:
                    logging.info(f"set_reset: could not find signal with name '{name}' among {defined_fields.keys()}. Default value (0) will be used")
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
        field_vals = self.field_values()
        res, off = 0, 0
        for name, width, *_ in self.layout:
            if not any(x in name for x in self.excluded_from_init):
                res |= field_vals[name] << off
            off += width
        return res

    def sanity_check(self):
        fields = self.field_values()
        for name, *_ in self.layout:
            if any(x in name for x in self.excluded_from_init):
                continue # zero-initialized, don't bother
            val = fields.get(name, None)
            if val is None:
                raise ValueError(f"RegisterReadValue: field '{name}' not initialized! Need {[x[0] for x in self.layout]}, got {fields}")

class RegisterCSR():
    def __init__(self, csr_idx, layout, reset_value_t):
        self._reset_value : RegisterResetValue= reset_value_t(layout)
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
    def handle_write(self):
        self.handler_notify_comb()

class MISA(ReadOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {
                "mxl": MisaRXL.RV32,
                "extensions": MisaExtensionBit.INTEGER_BASE_ISA,
            }
    def __init__(self):
        super().__init__(CSRIndex.MISA, misa_layout, __class__.RegValueLocal)


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
            return {
                "value": 0x0
            }
    def __init__(self):
        super().__init__(CSRIndex.MTVAL, flat_layout, __class__.RegValueLocal)

class MEPC(ReadOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {
                "value": 0x0
            }
    def __init__(self):
        super().__init__(CSRIndex.MEPC, flat_layout, __class__.RegValueLocal)

class MSCRATCH(RegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {
                "value": 0x0,
            }
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
            return {
                "value": 0x0
            }
    def __init__(self):
        super().__init__(CSRIndex.MHARTID, flat_layout, __class__.RegValueLocal)

class MCAUSE(ReadOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {
                "ecode": 0x0,
                "interrupt" : 0x0,
            }
    def __init__(self):
        super().__init__(CSRIndex.MCAUSE, mcause_layout, __class__.RegValueLocal)
