from pathlib import Path
import logging

class Config:
    git_root = Path(__file__).parent.parent.absolute()
    sw_dir = Path(git_root / "sw")
    bsp_dir = Path(sw_dir / "bsp")
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
