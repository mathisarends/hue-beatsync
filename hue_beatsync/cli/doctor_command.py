import asyncio

import click

from hue_beatsync.cli.output import Output, OutputMode
from hue_beatsync.diagnostics import diagnose_audio


@click.command()
@click.option("--device", help="Input device index or part of its name.")
@click.option(
    "--seconds",
    type=click.FloatRange(min=0.0, min_open=True),
    default=5.0,
    show_default=True,
    help="Finite measurement duration.",
)
@click.option("--interval", type=click.FloatRange(min=0.05), default=0.1, hidden=True)
@click.option(
    "--exclusive", is_flag=True, help="Request direct WASAPI hardware access."
)
@click.option(
    "--gain",
    type=click.FloatRange(min=0.0, min_open=True),
    default=1.0,
    show_default=True,
)
@click.pass_obj
def doctor(
    output: Output,
    device: str | None,
    seconds: float,
    interval: float,
    exclusive: bool,
    gain: float,
) -> None:
    """Check audio capture and show analyzed features."""
    listener = output.live_features if output.mode is OutputMode.HUMAN else None
    try:
        result = asyncio.run(
            diagnose_audio(
                device,
                duration=seconds,
                interval=interval,
                exclusive=exclusive,
                gain=gain,
                listener=listener,
            )
        )
        output.audio_diagnostic(result)
    except (RuntimeError, ValueError) as error:
        output.error(error)
        raise click.exceptions.Exit(1) from error
