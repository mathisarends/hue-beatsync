import json
import sys
from collections.abc import Iterable
from enum import StrEnum
from typing import Any

import click

from hue_beatsync.areas import BeatSyncArea
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

    def areas(self, areas: Iterable[BeatSyncArea]) -> None:
        items = list(areas)
        if self.mode is OutputMode.JSON:
            self._json([_area_data(area) for area in items])
            return
        if self.mode is OutputMode.PLAIN:
            for area in items:
                self._plain(area.id, area.name, area.active, area.channels)
            return
        if not items:
            click.echo("No entertainment areas found.")
            return
        for area in items:
            state = "active" if area.active else "inactive"
            click.echo(f"{area.name}  {state}  {area.channels} ch  {area.id}")

    def started(self, area: str, mode: str) -> None:
        data = {"status": "running", "area": area, "visual": mode}
        if self.mode is OutputMode.JSON:
            self._json(data)
        elif self.mode is OutputMode.PLAIN:
            self._plain(data["status"], area, mode)
        else:
            click.echo(f"Streaming {mode} to {area}. Press Ctrl+C to stop.")

    def stopped(self, area: str) -> None:
        data = {"status": "stopped", "area": area}
        if self.mode is OutputMode.JSON:
            self._json(data)
        elif self.mode is OutputMode.PLAIN:
            self._plain(data["status"], area)
        else:
            click.echo(f"Stopped streaming to {area}.")

    def error(self, error: BaseException) -> None:
        if self.mode is OutputMode.JSON:
            data = {"error": str(error)}
            if areas := getattr(error, "areas", None):
                data["areas"] = list(areas)
            self._json(data, err=True)
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


def _area_data(area: BeatSyncArea) -> dict[str, object]:
    return {
        "id": area.id,
        "name": area.name,
        "active": area.active,
        "channels": area.channels,
    }


def _escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")
