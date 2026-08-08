import sys


def main() -> None:
    try:
        from hue_beatsync.cli.app import cli
    except ModuleNotFoundError as error:
        if error.name != "click":
            raise
        print(
            "The command line interface requires the optional 'cli' extra. "
            "Install it with 'pip install hue-beatsync[cli]'.",
            file=sys.stderr,
        )
        raise SystemExit(1) from error

    cli()


__all__ = ["main"]
