import json
import sys
from collections.abc import Iterable
from enum import StrEnum
from typing import Any

import click

from hue_beatsync.audio import AudioDevice


class OutputMode(StrEnum):
    HUMAN = "human"
    PLAIN = "plain"
    JSON = "json"


class Output:
    def __init__(self, mode: OutputMode) -> None:
        self.mode = mode

    def devices(self, devices: Iterable[AudioDevice]) -> None:
        items = list(devices)
        if self.mode is OutputMode.JSON:
            self._json([_device_data(device) for device in items])
            return
        if self.mode is OutputMode.PLAIN:
            for device in items:
                self._plain(
                    device.index,
                    device.name,
                    device.samplerate,
                    device.channels,
                    device.host_api,
                )
            return
        if not items:
            click.echo("No audio input devices found.")
            return
        for device in items:
            click.echo(
                f"{device.index:>3}  {device.name}  "
                f"{device.samplerate} Hz  {device.channels} ch  {device.host_api}"
            )

    def visuals(self, names: Iterable[str]) -> None:
        items = list(names)
        if self.mode is OutputMode.JSON:
            self._json(items)
            return
        for name in items:
            click.echo(name)

    def started(self, area: str, mode: str) -> None:
        data = {"status": "running", "area": area, "visual": mode}
        if self.mode is OutputMode.JSON:
            self._json(data)
        elif self.mode is OutputMode.PLAIN:
            self._plain(data["status"], area, mode)
        else:
            click.echo(f"Streaming {mode} to {area}. Press Ctrl+C to stop.")

    def error(self, error: BaseException) -> None:
        if self.mode is OutputMode.JSON:
            self._json({"error": str(error)}, err=True)
        else:
            click.echo(f"Error: {error}", err=True)

    def _json(self, value: Any, *, err: bool = False) -> None:
        click.echo(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")),
            file=sys.stderr if err else None,
        )

    def _plain(self, *values: object) -> None:
        click.echo("\t".join(_escape(value) for value in values))


def _device_data(device: AudioDevice) -> dict[str, object]:
    return {
        "index": device.index,
        "name": device.name,
        "sample_rate": device.samplerate,
        "channels": device.channels,
        "host_api": device.host_api,
    }


def _escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")
