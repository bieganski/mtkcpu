from dataclasses import dataclass
from typing import List, Tuple
from nmigen import Module, Signal

@dataclass(frozen=True)
class MMIORegion:
    name : str
    start_addr : int
    num_bytes : int
    description : str

    def first_valid_byte_addr(self):
        return self.start_addr

    def last_valid_byte_addr(self):
        return self.start_addr + self.num_bytes - 1

    def bsp_constexpr_get_name(self):
        return f"{self.name}_addr"
    
    def bsp_constexpr_get_size_bytes_name(self):
        return f"{self.name}_num_bytes"

    def bsp_define_get_name(self):
        return f"__{self.bsp_constexpr_get_name()}"
    
    def bsp_define_get_size_bytes_name(self):
        return f"__{self.bsp_define_get_size_bytes_name()}"


@dataclass(frozen=True)
class MMIORegister:
    name : str
    addr : int
    description : str
    bitfield_t = Tuple[str, int] # name, offset, e.g. ('led_g', 10) if green led is mapped at 10-th bit of register 
    bits : List[bitfield_t]
    
    def bsp_define_get_name(self):
        return f"__{self.bsp_constexpr_get_name()}"

    def bsp_constexpr_get_name(self):
        return f"{self.name}_addr"

@dataclass(frozen=False)
class MMIOPeriphConfig:
    regions : List[MMIORegion]
    registers : List[MMIORegister]


@dataclass(frozen=True)
class MMIOAddressSpace:
    basename : str # basename.h and basename.cc will be created
    first_valid_addr_incl: int
    last_valid_addr_excl: int
    ws : int

    def bsp_get_base_define_name(self):
        return f"{self.basename}_base"

    def bsp_define_base(self):
        return f"#define {self.bsp_get_base_define_name()} {hex(self.first_valid_addr_incl)}"


    def sanity_check(self):
        begin, end = self.first_valid_addr_incl, self.last_valid_addr_excl
        if (begin - end) % self.ws != 0:
            raise ValueError(f"wrong addressing scheme passed!")
        if begin >= end:
            raise ValueError(f"begin >= end: {begin} >= {end}")

    def __post_init__(self):
        self.sanity_check()

    @property
    def num_words(self):
        self.sanity_check()
        diff = self.last_valid_addr_excl - self.first_valid_addr_incl
        return diff // 4


class DecoderInterface:
    def port(cfg : MMIOAddressSpace):
        raise NotImplementedError()


from mtkcpu.units.loadstore import BusSlaveOwnerInterface
from mtkcpu.units.mmio.bspgen import BspGeneratable

class AddressManager:
    def get_mmio_devices_config(self) -> List[Tuple[BusSlaveOwnerInterface, MMIOAddressSpace]]:
        raise NotImplementedError("AddressingGeneratable instance must overload get_mmio_devices_config method!")

    def __gen_addr_bsp(self):
        pass

    def gen_bsp(self):
        lst = self.get_mmio_devices_config()
        self.__gen_addr_bsp()
        devs, addresses = zip(*lst) # unzip.
        cfgs = [d.get_periph_config() for d in devs]
        for dev, addr in zip(cfgs, addresses):
            cfg = dev.get_periph_config()

    # must be called before 'elaborate' of each MMIO periph.
    def initialize_mmio_devices(self, decoder : DecoderInterface, top_module : Module):
        # self.sanity_check()
        lst = self.get_mmio_devices_config()
        for owner, addr_cfg in lst:
            name = addr_cfg.basename
            setattr(self, name, owner)
            setattr(top_module, name, owner)
            bus = decoder.port(addr_cfg)
            owner.init_bus_slave(bus)

    @staticmethod
    def __check_in_range(owner : BusSlaveOwnerInterface, addr_space : MMIOAddressSpace):
        name = addr_space.basename
        if isinstance(owner, BspGeneratable):
            cfg = owner.get_periph_config()
            for r in cfg.registers:
                pass
            for r in cfg.regions:
                reg_first = r.first_valid_byte_addr()
                reg_last = r.last_valid_byte_addr()
                space_first = addr_space.first_valid_addr_incl
                space_last = addr_space.last_valid_addr_excl
                if reg_first < space_first:
                    raise ValueError(f"MMIO device {name}: region {r.name} begin addr {reg_first} lower than address space ({space_first})")
                if reg_last > space_last:
                    raise ValueError(f"MMIO device {name}: region {r.name} end addr {reg_last} higher than address space max ({space_last})")

    def sanity_check(self):
        lst = self.get_mmio_devices_config()
        names = [x[1].basename for x in lst]
        if len(set(names)) != len(lst):
            raise ValueError(f"Two MMIO device with same name passed!")
        
        for dev, addr_space in lst:
            __class__.__check_in_range(dev, addr_space)

