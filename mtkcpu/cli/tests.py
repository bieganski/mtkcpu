from typing import Optional

from pytest import main as run_tests
import typer

tests_cli = typer.Typer()


@tests_cli.command("cpu")
def run_cpu_tests(
    elf_file: Optional[str] = typer.Argument(
        None, help="Simulate given ELF binary"
    ),
):
    run_tests([])
