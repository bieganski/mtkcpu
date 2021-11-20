from pathlib import Path
from subprocess import Popen, PIPE

class Config:
  git_root = Path(Popen(['git', 'rev-parse', '--show-toplevel'], stdout=PIPE).communicate()[0].rstrip().decode('utf-8'))
  sw_dir = git_root / "sw"
  bsp_dir = sw_dir / "bsp"
  linker_path = sw_dir / "linker.ld"
  after_main_sym_name = "mainDone"
