import asyncio
from typing import Any

import click

from hue_beatsync import BeatSync, input_devices, visual_names
from hue_beatsync.cli.output import Output, OutputMode


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="hue-beatsync")
@click.option("json_output", "--json", is_flag=True, help="Emit compact JSON.")
@click.option("plain", "--plain", is_flag=True, help="Emit stable tab-separated data.")
@click.pass_context
def cli(context: click.Context, json_output: bool, plain: bool) -> None:
    """Drive Philips Hue entertainment lights from live audio."""
    if json_output and plain:
        raise click.UsageError("--json and --plain cannot be used together")
    mode = (
        OutputMode.JSON
        if json_output
        else OutputMode.PLAIN
        if plain
        else OutputMode.HUMAN
    )
    context.obj = Output(mode)


@cli.command()
@click.argument("area")
@click.option("--device", help="Input device index or part of its name.")
@click.option(
    "--visual",
    "mode",
    type=click.Choice(visual_names()),
    default="pulse",
    show_default=True,
)
@click.option(
    "--seconds", type=click.FloatRange(min=0.0), help="Stop after this many seconds."
)
@click.option(
    "--rate",
    type=click.IntRange(min=1),
    default=50,
    show_default=True,
    help="Frames per second.",
)
@click.option(
    "--sensitivity", type=click.FloatRange(min=0.0), default=1.2, show_default=True
)
@click.option(
    "--gamma",
    type=click.FloatRange(min=0.0, min_open=True),
    default=1.0,
    show_default=True,
)
@click.option(
    "--floor", type=click.FloatRange(0.0, 1.0), default=0.12, show_default=True
)
@click.option(
    "--max-frequency",
    type=click.FloatRange(min=0.0, min_open=True),
    default=14_000.0,
    show_default=True,
)
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
def run(output: Output, area: str, **settings: Any) -> None:
    """Stream an audio-reactive visual to AREA."""
    try:
        asyncio.run(_run(output, area, settings))
    except (RuntimeError, ValueError) as error:
        output.error(error)
        raise click.exceptions.Exit(1) from error


@cli.group()
def devices() -> None:
    """Inspect audio input devices."""


@devices.command("list")
@click.pass_obj
def list_devices(output: Output) -> None:
    """List available audio inputs."""
    try:
        output.devices(input_devices())
    except RuntimeError as error:
        output.error(error)
        raise click.exceptions.Exit(1) from error


@cli.group()
def visuals() -> None:
    """Inspect available light visuals."""


@visuals.command("list")
@click.pass_obj
def list_visuals(output: Output) -> None:
    """List visual names accepted by the run command."""
    output.visuals(visual_names())


async def _run(output: Output, area: str, settings: dict[str, Any]) -> None:
    seconds = settings.pop("seconds")
    sync = BeatSync(area, **settings)
    async with sync:
        output.started(area, sync.mode)
        await sync.run(seconds)
