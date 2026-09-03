import json
import sys
from collections.abc import Iterable
from enum import StrEnum
from typing import Any

import click

from hue_beatsync.analysis import BAND_NAMES, AudioFeatures
from hue_beatsync.areas import BeatSyncArea
from hue_beatsync.audio import AudioDevice
from hue_beatsync.diagnostics import AudioDiagnostic


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

    def live_features(self, elapsed: float, features: AudioFeatures) -> None:
        if not click.get_text_stream("stdout").isatty():
            return
        bands = " ".join(_meter(level) for level in features.levels)
        bpm = f"{features.bpm:.0f}" if features.bpm is not None else "--"
        click.echo(
            f"\r{elapsed:4.1f}s  {bands}  beats {features.beats}  bpm {bpm}",
            nl=False,
        )

    def audio_diagnostic(self, result: AudioDiagnostic) -> None:
        data = _diagnostic_data(result)
        if self.mode is OutputMode.JSON:
            self._json(data)
            return
        if self.mode is OutputMode.PLAIN:
            self._plain(
                result.device.index,
                result.device.name,
                result.audio_detected,
                result.beats,
                _rounded(result.bpm),
                result.dropouts,
                *(_rounded(level) for level in result.levels),
            )
            return
        if click.get_text_stream("stdout").isatty():
            click.echo()
        signal = "detected" if result.audio_detected else "not detected"
        bpm = f"{result.bpm:.1f}" if result.bpm is not None else "not enough beats"
        click.echo(f"Audio {signal} on [{result.device.index}] {result.device.name}")
        click.echo(
            f"Beats {result.beats}  BPM {bpm}  "
            f"latency {result.latency_ms:.1f} ms  dropouts {result.dropouts}"
        )
        for name, level in zip(BAND_NAMES, result.levels, strict=True):
            click.echo(f"{name:>8}  {_meter(level)}  {level:.2f}")

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


def _diagnostic_data(result: AudioDiagnostic) -> dict[str, object]:
    return {
        "device": {"index": result.device.index, "name": result.device.name},
        "duration": result.duration,
        "audio": result.audio_detected,
        "beats": result.beats,
        "bpm": _rounded(result.bpm),
        "dropouts": result.dropouts,
        "latency_ms": _rounded(result.latency_ms),
        "features": {
            "loudness": _rounded(result.max_loudness),
            "energy": _rounded(result.max_energy),
            "percussiveness": _rounded(result.max_percussiveness),
            "bands": {
                name: _rounded(level)
                for name, level in zip(BAND_NAMES, result.levels, strict=True)
            },
        },
    }


def _rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _meter(value: float, width: int = 8) -> str:
    filled = round(min(max(value, 0.0), 1.0) * width)
    return "█" * filled + "░" * (width - filled)


def _escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")
