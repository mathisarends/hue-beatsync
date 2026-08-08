"""Microphone capture as a stream of mono blocks.

PortAudio calls us back on its own high priority thread. That callback must
never block, so it does the cheap part - downmix to mono - and hands the block
straight to a listener.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Self

import numpy as np
import sounddevice as sd

DEFAULT_BLOCK_SIZE = 512

type BlockListener = Callable[[np.ndarray, float], None]


@dataclass(frozen=True, slots=True)
class AudioDevice:
    index: int
    name: str
    samplerate: int
    channels: int
    host_api: str

    def __str__(self) -> str:
        return f"[{self.index}] {self.name} ({self.host_api}, {self.samplerate} Hz)"


def input_devices() -> list[AudioDevice]:
    host_apis = sd.query_hostapis()
    return [
        AudioDevice(
            index=index,
            name=device["name"].strip(),
            samplerate=round(device["default_samplerate"]),
            channels=device["max_input_channels"],
            host_api=host_apis[device["hostapi"]]["name"],
        )
        for index, device in enumerate(sd.query_devices())
        if device["max_input_channels"] > 0
    ]


def resolve_device(wanted: int | str | None = None) -> AudioDevice:
    """Pick an input by index, by a piece of its name, or take the default."""
    devices = input_devices()
    if not devices:
        raise RuntimeError("No audio input device found")

    if wanted is None:
        default = sd.default.device[0]
        return next(
            (device for device in devices if device.index == default), devices[0]
        )

    if isinstance(wanted, str) and wanted.isdigit():
        wanted = int(wanted)

    if isinstance(wanted, int):
        match = next((device for device in devices if device.index == wanted), None)
    else:
        needle = wanted.casefold()
        match = next(
            (device for device in devices if needle in device.name.casefold()), None
        )

    if match is None:
        listing = "\n  ".join(str(device) for device in devices)
        raise RuntimeError(
            f"No input device matches {wanted!r}. Available:\n  {listing}"
        )
    return match


class AudioCapture:
    """An open input stream that pushes mono blocks to a listener."""

    def __init__(
        self,
        device: AudioDevice,
        listener: BlockListener,
        block_size: int = DEFAULT_BLOCK_SIZE,
    ) -> None:
        self.device = device
        self.block_size = block_size
        self._listener = listener
        self._stream: sd.InputStream | None = None
        self._failure: BaseException | None = None
        self._dropouts = 0

    @property
    def samplerate(self) -> int:
        return self.device.samplerate

    @property
    def latency(self) -> float:
        """Seconds between a sound happening and its block arriving."""
        if self._stream is None:
            return self.block_size / self.samplerate
        return self._stream.latency + self.block_size / self.samplerate

    @property
    def dropouts(self) -> int:
        """How often the input overflowed, a sign the analysis is too slow."""
        return self._dropouts

    @property
    def failure(self) -> BaseException | None:
        return self._failure

    def start(self) -> Self:
        self._stream = sd.InputStream(
            device=self.device.index,
            channels=min(self.device.channels, 2),
            samplerate=self.samplerate,
            blocksize=self.block_size,
            dtype="float32",
            latency="low",
            callback=self._on_block,
        )
        self._stream.start()
        return self

    def stop(self) -> None:
        if self._stream is None:
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.stop()

    def _on_block(
        self, indata: np.ndarray, frames: int, _time: object, status: sd.CallbackFlags
    ) -> None:
        if status.input_overflow:
            self._dropouts += 1

        # mean() copies, which matters: PortAudio reuses the input buffer.
        mono = indata.mean(axis=1, dtype=np.float32)
        try:
            self._listener(mono, frames / self.samplerate)
        except Exception as error:
            # PortAudio would tear the stream down silently, so keep the reason.
            self._failure = error
