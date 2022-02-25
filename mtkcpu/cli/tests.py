from typing import Optional

from pytest import main as run_tests
import typer

tests_cli = typer.Typer()

from .top import generate_bsp

@tests_cli.command("cpu")
def run_cpu_tests(
    elf_file: Optional[str] = typer.Argument(
        None, help="Simulate given ELF binary"
    ),
):

    generate_bsp()
    run_tests([])
