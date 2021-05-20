import typer

from .tests import tests_cli


def get_typer_cli() -> typer.Typer:
    cli = typer.Typer()
    cli.add_typer(tests_cli, name="tests")
    return cli


def run_cli():
    get_typer_cli()()


if __name__ == "__main__":
    run_cli()
