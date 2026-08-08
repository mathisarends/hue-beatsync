from dataclasses import dataclass
from importlib import import_module
from types import TracebackType
from typing import Any, Self

import numpy as np

from hue_beatsync.audio.ports import BlockListener

_DEFAULT_BLOCK_SIZE = 512


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
    sd = _load_sounddevice()
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
        default = _load_sounddevice().default.device[0]
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


class SoundDeviceCapture:
    """A sounddevice input stream that pushes mono blocks to a listener."""

    def __init__(
        self,
        device: AudioDevice,
        listener: BlockListener,
        block_size: int = _DEFAULT_BLOCK_SIZE,
    ) -> None:
        if block_size <= 0:
            raise ValueError("block_size must be positive")
        self.device = device
        self.block_size = block_size
        self._listener = listener
        self._stream: Any | None = None
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
        sd = _load_sounddevice()
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
        self, indata: np.ndarray, frames: int, _time: object, status: Any
    ) -> None:
        if status.input_overflow:
            self._dropouts += 1

        mono = indata.mean(axis=1, dtype=np.float32)
        try:
            self._listener(mono, frames / self.samplerate)
        except Exception as error:
            self._failure = error


def _load_sounddevice() -> Any:
    try:
        return import_module("sounddevice")
    except ModuleNotFoundError as error:
        if error.name != "sounddevice":
            raise
        raise RuntimeError(
            "The sounddevice backend requires the optional 'sounddevice' extra. "
            "Install it with 'pip install hue-beatsync[sounddevice]'."
        ) from error
