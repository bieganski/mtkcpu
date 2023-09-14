from typing import Dict

from amaranth import Signal, Module, Elaboratable
from amaranth.hdl.rec import Record

from mtkcpu.cpu.priv_isa import *
from mtkcpu.utils.common import CODE_START_ADDR



class Controller():
    def __init__(self) -> None:
        self.command_finished   = Signal()




class CSR_Write_Handler(Elaboratable):
    def __init__(self, command_finished: Signal):
        # -- Input signals
        # 
        # Needs to be deasserted in cycle following 'controller.cmd_finished' asserted.
        self.active = Signal()
        self.write_value = Signal(32)

    def elaborate(self):
        raise NotImplementedError()
    













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
                if reset_val is not None:
                    sig.reset = reset_val
            elif isinstance(sig, Record):
                assert False
                self.set_reset(sig)
            else:
                assert False

    @staticmethod
    def calc_reset_value(fields: Dict[str, int], layout: List[Tuple[str, int]]) -> int:
        res, off = 0, 0
        for name, width, *_ in layout:
            res |= (fields.get(name, 0) & ((1 << width) - 1)) << off
            off += width
        return res

    @staticmethod
    def value_to_fields(value: int, layout: List[Tuple[str, int]]) -> Dict[str, int]:
        res = {}
        aux_val = value
        for name, width, *_ in layout:
            res[name] = aux_val & ((1 << width) - 1)
            aux_val >>= width
        return res
    
    @property
    def value(self) -> int:
        return __class__.calc_reset_value(fields=self.field_values(), layout=self.layout)
        
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
        self._reset_value.set_reset(self.rec.w)
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

    # because of WARL sometimes we cannot copy whole record
    # TODO, should we overload it in ReadOnly/WriteOnly CSR registers to raise? Otherwise 'hasattr' will raise anyway.
    def copy_specific_fields_only(self, fields : List[str]):
        m = self.get_m()
        for f in fields:
            dst = getattr(self.rec.r, f)
            src = getattr(self.rec.w, f)
            m.d.sync += dst.eq(src)
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

class MTVEC(WriteOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {
                "mode": MtvecModeBits.DIRECT,
                "base": (CODE_START_ADDR + 0x20) >> 2
            }
    def __init__(self):
        super().__init__(CSRIndex.MTVEC, mtvec_layout, __class__.RegValueLocal)

    def handle_write(self):
        self.handler_notify_comb()

class MTVAL(ReadOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRIndex.MTVAL, flat_layout, __class__.RegValueLocal)

class MEPC(RegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRIndex.MEPC, flat_layout, __class__.RegValueLocal)

    def handle_write(self):
        m = self.get_m()
        m.d.sync += [
            self.rec.r.eq(self.rec.w)
        ]
        self.handler_notify_comb()

class DPC(RegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRIndex.DPC, flat_layout, __class__.RegValueLocal)

    def handle_write(self):
        m = self.get_m()
        m.d.sync += [
            self.rec.r.eq(self.rec.w)
        ]
        self.handler_notify_comb()


# dcsr_layout = [
#     ("prv",        2, CSRAccess.RW),
#     ("step",       1, CSRAccess.RW),
#     ("nmip",       1, CSRAccess.RO),
#     ("mprven",     1, CSRAccess.RW),
#     ("v",          1, CSRAccess.RW),
#     ("cause",      3, CSRAccess.RO),
#     ("stoptime",   1, CSRAccess.RW),
#     ("stopcount",  1, CSRAccess.RW),
#     ("stepie",     1, CSRAccess.RW),
#     ("ebreaku",    1, CSRAccess.RW),
#     ("ebreaks",    1, CSRAccess.RW),
#     ("zero1",      1, CSRAccess.RO)
#     ("ebreakm",    1, CSRAccess.RW),
#     ("ebreakvu",   1, CSRAccess.RW),
#     ("ebreakvs",   1, CSRAccess.RW),
#     ("zero2",     10, CSRAccess.RO),
#     ("debugver",   4, CSRAccess.RO), 
# ]

class DCSR(RegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {
                # For valid (prv, v) combination, refer to Debug Specs 1.0, table 4.6.
                "prv": 3,
                "v": 0,

                # From Debug Specs 1.0:
                # 4 - Debug support exists as it is described in this document.
                "debugver": 4,
            }
    def __init__(self):
        super().__init__(CSRIndex.DCSR, dcsr_layout, __class__.RegValueLocal)

    def handle_write(self):
        m = self.get_m()

        for x in ["step", "ebreakm"]:
            m.d.sync += [
                getattr(self.rec.r, x).eq(getattr(self.rec.w, x))
            ]
        self.handler_notify_comb()


class MSCRATCH(WriteOnlyRegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRIndex.MSCRATCH, flat_layout, __class__.RegValueLocal)

    def handle_write(self):
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


class SATP(RegisterCSR):
    class RegValueLocal(RegisterResetValue):
        def field_values(self):
            return {}
    def __init__(self):
        super().__init__(CSRIndex.SATP, satp_layout, __class__.RegValueLocal)

    def handle_write(self):
        self.copy_specific_fields_only(["ppn", "mode"])
