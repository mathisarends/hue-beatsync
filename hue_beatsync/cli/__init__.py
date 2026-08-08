import sys
from typing import Any


def command() -> Any:
    try:
        from hue_beatsync.cli.app import cli
        from hue_beatsync.cli.area_commands import areas, stop
    except ModuleNotFoundError as error:
        _missing_cli_dependency(error)

    if "areas" not in cli.commands:
        cli.add_command(areas)
        cli.add_command(stop)
    return cli


def main() -> None:
    command()()


def _missing_cli_dependency(error: ModuleNotFoundError) -> None:
    if error.name != "click":
        raise error
    print(
        "The command line interface requires the optional 'cli' extra. "
        "Install it with 'pip install hue-beatsync[cli]'.",
        file=sys.stderr,
    )
    raise SystemExit(1) from error


__all__ = ["command", "main"]
