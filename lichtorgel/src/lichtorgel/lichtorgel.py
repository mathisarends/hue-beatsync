import asyncio
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Self

from hueify import Hueify
from hueify.entertainment import EntertainmentStream

from lichtorgel.analysis import SpectralAnalyzer, band_edges
from lichtorgel.audio.sounddevice import (
    AudioDevice,
    SoundDeviceCapture,
    resolve_device,
)
from lichtorgel.visuals import Visual, channel_positions, create_visual

_DEFAULT_MODE = "pulse"
_DEFAULT_RATE = 50
_DEFAULT_SENSITIVITY = 1.2
_DEFAULT_GAMMA = 1.0
_DEFAULT_FLOOR = 0.12
_DEFAULT_MAX_FREQUENCY = 14_000.0
_FAILURE_POLL_INTERVAL = 0.05


class Lichtorgel:
    """Stream a sounddevice input to a Hue entertainment area."""

    def __init__(
        self,
        area_name: str,
        *,
        device: int | str | AudioDevice | None = None,
        mode: str = _DEFAULT_MODE,
        rate: int = _DEFAULT_RATE,
        sensitivity: float = _DEFAULT_SENSITIVITY,
        gamma: float = _DEFAULT_GAMMA,
        floor: float = _DEFAULT_FLOOR,
        max_frequency: float = _DEFAULT_MAX_FREQUENCY,
        exclusive: bool = False,
        gain: float = 1.0,
    ) -> None:
        if not area_name.strip():
            raise ValueError("area_name must not be empty")
        self.area_name = area_name
        self.device = (
            device if isinstance(device, AudioDevice) else resolve_device(device)
        )
        self.mode = mode
        self.rate = rate
        self.analyzer = SpectralAnalyzer(
            self.device.samplerate,
            sensitivity=sensitivity,
            edges=band_edges(max_frequency),
        )
        self.capture = SoundDeviceCapture(
            self.device, self.analyzer.feed, exclusive=exclusive, gain=gain
        )
        self.gamma = gamma
        self.floor = floor
        self.stream: EntertainmentStream | None = None
        self.visual: Visual | None = None
        self._stack: AsyncExitStack | None = None
        self._running = False

    async def __aenter__(self) -> Self:
        if self._stack is not None:
            raise RuntimeError("Lichtorgel is already open")

        stack = AsyncExitStack()
        try:
            hue = await stack.enter_async_context(Hueify())
            area = await hue.entertainment.find_by_name(self.area_name)
            if area.is_streaming:
                raise RuntimeError(
                    f"Entertainment area {self.area_name!r} is already streaming"
                )

            self.stream = await stack.enter_async_context(
                hue.entertainment.stream(area, rate=self.rate)
            )
            self.visual = create_visual(
                self.mode,
                channel_positions(self.stream.channels),
                self.analyzer,
                gamma=self.gamma,
                floor=self.floor,
            )
            stack.enter_context(self.capture)
        except BaseException:
            await stack.aclose()
            raise

        self._stack = stack
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        stack = self._stack
        self._stack = None
        if stack is None:
            return None
        return await stack.__aexit__(exc_type, exc_val, exc_tb)

    async def run(self, seconds: float | None = None) -> None:
        """Run until cancelled, the stream stops, or ``seconds`` elapse."""
        if self._running:
            raise RuntimeError("Lichtorgel is already running")
        if seconds is not None and seconds < 0:
            raise ValueError("seconds must not be negative")
        if self._stack is None or self.stream is None or self.visual is None:
            raise RuntimeError("use 'async with Lichtorgel(...)' before calling run()")

        self._running = True
        try:
            try:
                async with asyncio.timeout(seconds):
                    await self._run_stream(self.stream, self.visual)
            except TimeoutError:
                pass
        finally:
            self._running = False

    async def _run_stream(self, stream: EntertainmentStream, visual: Visual) -> None:
        stream_task = asyncio.create_task(stream.run(visual))
        failure_task = asyncio.create_task(self._wait_for_capture_failure())
        tasks = {stream_task, failure_task}
        try:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            for task in done:
                failure = task.result()
                if failure is not None:
                    raise failure
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _wait_for_capture_failure(self) -> BaseException:
        while self.capture.failure is None:
            await asyncio.sleep(_FAILURE_POLL_INTERVAL)
        return self.capture.failure
