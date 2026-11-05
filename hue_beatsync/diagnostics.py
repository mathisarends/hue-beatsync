import asyncio
import statistics
from collections.abc import Callable
from dataclasses import dataclass

from hue_beatsync.analysis import AudioFeatures, SpectralAnalyzer
from hue_beatsync.audio import AudioDevice, SoundDeviceCapture, resolve_device


@dataclass(frozen=True, slots=True)
class AudioDiagnostic:
    device: AudioDevice
    duration: float
    audio_detected: bool
    beats: int
    bpm: float | None
    dropouts: int
    latency_ms: float
    max_loudness: float
    max_energy: float
    max_percussiveness: float
    levels: tuple[float, ...]


async def diagnose_audio(
    device: int | str | AudioDevice | None = None,
    *,
    duration: float = 5.0,
    interval: float = 0.1,
    exclusive: bool = False,
    gain: float = 1.0,
    listener: Callable[[float, AudioFeatures], None] | None = None,
) -> AudioDiagnostic:
    if duration <= 0.0:
        raise ValueError("duration must be positive")
    if interval <= 0.0:
        raise ValueError("interval must be positive")

    resolved = device if isinstance(device, AudioDevice) else resolve_device(device)
    analyzer = SpectralAnalyzer(resolved.samplerate)
    capture = SoundDeviceCapture(
        resolved, analyzer.feed, exclusive=exclusive, gain=gain
    )
    samples: list[AudioFeatures] = []
    elapsed = 0.0
    initial_beats = analyzer.features.beats

    with capture:
        while elapsed < duration:
            step = min(interval, duration - elapsed)
            await asyncio.sleep(step)
            elapsed += step
            if capture.failure is not None:
                raise capture.failure
            features = analyzer.features
            samples.append(features)
            if listener is not None:
                listener(elapsed, features)

    return _summarize(resolved, duration, capture, initial_beats, samples)


def _summarize(
    device: AudioDevice,
    duration: float,
    capture: SoundDeviceCapture,
    initial_beats: int,
    samples: list[AudioFeatures],
) -> AudioDiagnostic:
    latest = samples[-1]
    bpms = [sample.bpm for sample in samples if sample.bpm is not None]
    levels = tuple(
        max(sample.levels[index] for sample in samples)
        for index in range(len(latest.levels))
    )
    return AudioDiagnostic(
        device=device,
        duration=duration,
        audio_detected=any(not sample.silent for sample in samples),
        beats=max(latest.beats - initial_beats, 0),
        bpm=statistics.median(bpms) if bpms else None,
        dropouts=capture.dropouts,
        latency_ms=capture.latency * 1000.0,
        max_loudness=max(sample.loudness for sample in samples),
        max_energy=max(sample.energy for sample in samples),
        max_percussiveness=max(sample.percussiveness for sample in samples),
        levels=levels,
    )
