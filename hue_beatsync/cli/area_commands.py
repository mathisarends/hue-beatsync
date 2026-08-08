import asyncio

import click
import httpx
from hueify.errors import HueifyError

from hue_beatsync.areas import list_areas, stop_area
from hue_beatsync.cli.output import Output


@click.group()
def areas() -> None:
    """Inspect Hue entertainment areas."""


@areas.command("list")
@click.pass_obj
def list_entertainment_areas(output: Output) -> None:
    """List areas that can run an entertainment stream."""
    try:
        output.areas(asyncio.run(list_areas()))
    except (HueifyError, httpx.HTTPError, RuntimeError, ValueError) as error:
        _fail(output, error)


@click.command()
@click.argument("area")
@click.pass_obj
def stop(output: Output, area: str) -> None:
    """Release AREA and stop its entertainment stream."""
    try:
        stopped = asyncio.run(stop_area(area))
        output.stopped(stopped.name)
    except (HueifyError, httpx.HTTPError, RuntimeError, ValueError) as error:
        _fail(output, error)


def _fail(output: Output, error: BaseException) -> None:
    output.error(error)
    raise click.exceptions.Exit(1) from error
