from pathlib import Path
from subprocess import Popen, PIPE
import logging

class Config:
    git_root = Path(Popen(['git', 'rev-parse', '--show-toplevel'], stdout=PIPE).communicate()[0].rstrip().decode('utf-8'))
    sw_dir = Path(git_root / "sw")
    bsp_dir = Path(sw_dir / "bsp")
    linker_script_tpl_path = Path(sw_dir / "common" / "linker.ld.jinja2")
    after_main_sym_name = "mainDone"

    @staticmethod
    def sanity_check():
        for x in dir(__class__):
            if not x.startswith("_"):
                x = getattr(Config, x)
                if isinstance(x, Path):
                    if x.exists():
                        logging.info(f"Config sanity check: OK, {x} exists..")
                    else:
                        raise ValueError(f"Config sanity check failed: {x} does not exists!")
        logging.info("Config sanity check passed!")

    @staticmethod
    def write_linker_script(out_path : Path, mem_addr : int):
        import jinja2
        __class__.sanity_check()
        logging.info(f"writing linker script: using {hex(mem_addr)} address..")
        linker_script_content = jinja2.Template(
            __class__.linker_script_tpl_path.open("r").read()).render(template_mem_start_addr=hex(mem_addr)) 
        out_path.open("w").write(linker_script_content)
        logging.info(f"OK, linker script written to {out_path} file!")
