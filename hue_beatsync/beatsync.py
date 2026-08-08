import asyncio

from hueify import Hueify
from hueify.entertainment import EntertainmentStream
from hueify.models import EntertainmentConfiguration

from hue_beatsync.analysis import SpectralAnalyzer, band_edges
from hue_beatsync.audio.sounddevice import (
    AudioDevice,
    SoundDeviceCapture,
    resolve_device,
)
from hue_beatsync.visuals import Visual, channel_positions, create_visual

_DEFAULT_MODE = "pulse"
_DEFAULT_RATE = 50
_DEFAULT_SENSITIVITY = 1.2
_DEFAULT_GAMMA = 1.0
_DEFAULT_MAX_FREQUENCY = 14_000.0
_FAILURE_POLL_INTERVAL = 0.05


class BeatSync:
    """Stream a sounddevice input to a Hue entertainment area."""

    def __init__(
        self,
        area: str | EntertainmentConfiguration,
        *,
        hue: Hueify | None = None,
        device: int | str | AudioDevice | None = None,
        mode: str = _DEFAULT_MODE,
        rate: int = _DEFAULT_RATE,
        sensitivity: float = _DEFAULT_SENSITIVITY,
        gamma: float = _DEFAULT_GAMMA,
        max_frequency: float = _DEFAULT_MAX_FREQUENCY,
        exclusive: bool = False,
        gain: float = 1.0,
    ) -> None:
        self.area = area
        self.hue = hue
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
        self.stream: EntertainmentStream | None = None
        self.visual: Visual | None = None
        self._running = False

    async def run(self, seconds: float | None = None) -> None:
        """Run until cancelled, the stream stops, or ``seconds`` elapse."""
        if self._running:
            raise RuntimeError("BeatSync is already running")
        if seconds is not None and seconds < 0:
            raise ValueError("seconds must not be negative")

        self._running = True
        try:
            if self.hue is None:
                async with Hueify() as hue:
                    await self._run(hue, seconds)
            else:
                await self._run(self.hue, seconds)
        finally:
            self._running = False

    async def _run(self, hue: Hueify, seconds: float | None) -> None:
        area = self.area
        if isinstance(area, str):
            area = await hue.entertainment.find_by_name(area)
        if area.is_streaming:
            raise RuntimeError(f"Entertainment area {area.name!r} is already streaming")

        async with hue.entertainment.stream(area, rate=self.rate) as stream:
            self.stream = stream
            self.visual = create_visual(
                self.mode,
                channel_positions(stream.channels),
                self.analyzer,
                gamma=self.gamma,
            )
            with self.capture:
                try:
                    async with asyncio.timeout(seconds):
                        await self._run_stream(stream, self.visual)
                except TimeoutError:
                    pass

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
