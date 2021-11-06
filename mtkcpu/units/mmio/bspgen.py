from dataclasses import dataclass
from typing import List, Tuple
from pathlib import Path

@dataclass(frozen=True)
class MMIORegion:
    name : str
    start_addr : int
    num_bytes : int
    description : str

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
    basename : str # basename.h and basename.cc will be created
    regions : List[MMIORegion]
    registers : List[MMIORegister]
    first_valid_addr: int
    last_valid_addr: int

    def bsp_get_base_define_name(self):
        return f"{self.basename}_base"

    def bsp_define_base(self):
        return f"#define {self.bsp_get_base_define_name()} {hex(self.first_valid_addr)}"

# MMIO devices derive that class.
class BspGeneratable:
    def get_periph_config(self) -> MMIOPeriphConfig:
        raise NotImplementedError("ERROR: To generate code for MMIO device you need to overload get_periph_config function!")

@dataclass(frozen=True)
class MemMapCodeGen:
    periph_configs : List[MMIOPeriphConfig]
    dir = Path("bsp")
    log = print

    def get_cc_path(self, cfg : MMIOPeriphConfig) -> Path:
        return Path(self.dir / f"{cfg.basename}.cc")

    def get_h_path(self, cfg : MMIOPeriphConfig) -> Path:
        return Path(self.dir / f"{cfg.basename}.h")

    # TODO fix generation for bits
    def __generate_h(self, cfg : MMIOPeriphConfig):
        codelines = []
        codelines.append("// Code automatically generated, do not modify!\n")
        codelines.append(cfg.bsp_define_base())
        for reg in cfg.registers:
            comment = f"/* {reg.description} */"
            line = f"#define {reg.bsp_define_get_name()} ({cfg.bsp_get_base_define_name()} + {hex(reg.addr)})"
            codelines.extend([comment, line, ""])
            for name, offset in reg.bits:
                line = f"#define __{name}_{reg.bsp_define_get_name()}_offset {offset}"
                codelines.extend([line, ""])
        for area in cfg.regions:
            comment = f"/* {area.description} */"
            ptr = f"#define {area.bsp_define_get_name()} {hex(area.start_addr)}"
            size = f"#define {area.bsp_define_get_size_bytes_name()} {hex(area.num_bytes)}"
            codelines.extend([comment, ptr, size, ""])
        self.get_h_path(cfg).open("w").writelines([x + '\n' for x in codelines])

    # TODO fix generation for bits
    def __generate_cc(self, cfg : MMIOPeriphConfig):
        codelines = []
        codelines.append("// Code automatically generated, do not modify!\n")
        codelines.append(f'#include "{self.get_h_path(cfg).name}"') # it works under assumption that .cc and .h are in same dirs.
        for reg in cfg.registers:
            comment = f"/* {reg.description} */"
            constname, defname = reg.bsp_constexpr_get_name(), reg.bsp_define_get_name()
            line = f"const void* {constname} = (void*) {defname};"
            codelines.extend([comment, line, ""])
            for name, _ in reg.bits:
                name = f"{name}___{reg.bsp_constexpr_get_name()}_offset"
                line = f"constexpr unsigned {name} = (unsigned) __{name};"
                codelines.extend([line, ""])

        for area in cfg.regions:
            defptrname, defsizename = area.bsp_define_get_name(), area.bsp_define_get_size_bytes_name()
            constptrname, constsizename = area.bsp_constexpr_get_name(), area.bsp_constexpr_get_size_bytes_name()
            comment = f"/* {area.description} */"
            ptr_line = f"const void* {constptrname} = (void*) {defptrname};"
            size_line = f"constexpr unsigned {constsizename} = (unsigned) {defsizename};"
            codelines.extend([comment, ptr_line, size_line, ""])
        self.get_cc_path(cfg).open("w").writelines([x + '\n' for x in codelines])

    def gen_bsp_sources(self):
        log = __class__.log
        cfgs = self.periph_configs
        
        log(f"starting bsp code generation inside {self.dir} directory..")
        self.dir.mkdir(exist_ok=True)
        log(f"found {len(cfgs)} peripherials..")
        for c in cfgs:
            log(f"generating {self.get_cc_path(c)}")
            self.__generate_cc(c)
            log(f"generating {self.get_h_path(c)}")
            self.__generate_h(c)
        log("ok, code generation done!")
