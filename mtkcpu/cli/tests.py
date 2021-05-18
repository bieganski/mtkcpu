from typing import Optional

import typer

tests_cli = typer.Typer()


@tests_cli.command("cpu")
def run_cpu_tests(
    elf_file: Optional[str] = typer.Argument(
        None, help="Simulate given ELF binary"
    ),
):
    pass
