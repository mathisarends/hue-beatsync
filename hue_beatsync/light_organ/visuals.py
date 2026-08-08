"""Frame sources that paint an entertainment area from audio features.

Each visual is a plain ``FrameSource``: it gets a frame and a tick, reads the
analyzer's latest snapshot and paints. The analyzer runs on the audio thread at
its own pace, so a visual never waits for audio - it draws whatever the most
recent snapshot says, smoothed over time.
"""

from __future__ import annotations

import colorsys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from hueify.color import RGB
from hueify.entertainment import Frame, Tick
from hueify.models import EntertainmentChannel

from light_organ.analysis import BAND_NAMES, AudioFeatures, SpectralAnalyzer
from light_organ.smoothing import Envelope

BAND_HUES = (0.0, 0.08, 0.30, 0.52, 0.75)
GOLDEN_ANGLE = 0.381966

# Brightness curve. 1.0 is linear; above that the quiet parts go dark and the
# beats stand out more, which costs overall brightness in the room.
DEFAULT_GAMMA = 1.0

_BAND_COUNT = len(BAND_NAMES)


def channel_positions(channels: Iterable[EntertainmentChannel]) -> dict[int, float]:
    """Where each channel sits on the left to right axis, from -1 to 1."""
    return {channel.channel_id: channel.position.x for channel in channels}


def hsv(hue: float, saturation: float = 1.0, value: float = 1.0) -> RGB:
    red, green, blue = colorsys.hsv_to_rgb(hue % 1.0, saturation, value)
    return (round(red * 255), round(green * 255), round(blue * 255))


class Visual:
    """Shared plumbing: channel geometry, the analyzer and beat bookkeeping."""

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = DEFAULT_GAMMA,
    ) -> None:
        self._positions = dict(positions)
        self._analyzer = analyzer
        self._gamma = gamma
        self._seen_beats = analyzer.features.beats

    def render(self, frame: Frame, tick: Tick) -> None:
        features = self._analyzer.features
        beats = features.beats - self._seen_beats
        self._seen_beats = features.beats
        self.paint(frame, tick, features, beats)

    def paint(
        self, frame: Frame, tick: Tick, features: AudioFeatures, beats: int
    ) -> None:
        raise NotImplementedError

    def _shape(self, level: float) -> float:
        """Bend a level into a brightness with a bit more contrast."""
        return min(max(level, 0.0), 1.0) ** self._gamma


class Spectrum(Visual):
    """The room becomes an equalizer: bass on the left, treble on the right.

    Channels rarely line up with the five bands, so each one sits at a
    fractional band index and mixes its two neighbours. With three lamps that
    reads as bass / mid / treble, with ten it becomes a gradient.
    """

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = DEFAULT_GAMMA,
    ) -> None:
        super().__init__(positions, analyzer, gamma)
        ordered = sorted(self._positions, key=lambda channel: self._positions[channel])
        span = max(len(ordered) - 1, 1)
        self._slots = {
            channel: index / span * (_BAND_COUNT - 1)
            for index, channel in enumerate(ordered)
        }
        self._envelopes = {channel: Envelope(0.02, 0.18) for channel in ordered}

    def paint(
        self, frame: Frame, tick: Tick, features: AudioFeatures, beats: int
    ) -> None:
        for channel, slot in self._slots.items():
            lower = int(slot)
            upper = min(lower + 1, _BAND_COUNT - 1)
            blend = slot - lower

            level = _mix(features.levels[lower], features.levels[upper], blend)
            hue = _mix(BAND_HUES[lower], BAND_HUES[upper], blend)
            smoothed = self._envelopes[channel].update(level, tick.delta)
            frame.set(channel, hsv(hue), self._shape(smoothed))


class Pulse(Visual):
    """The whole room breathes with the bass and shifts color on every beat.

    The hue walks by the golden angle instead of cycling a fixed palette, which
    keeps consecutive beats far apart in color without ever repeating a loop.
    """

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = DEFAULT_GAMMA,
    ) -> None:
        super().__init__(positions, analyzer, gamma)
        self._brightness = Envelope(0.015, 0.22)
        self._flash = Envelope(0.005, 0.12)
        self._hue = 0.0

    def paint(
        self, frame: Frame, tick: Tick, features: AudioFeatures, beats: int
    ) -> None:
        if beats:
            self._hue += GOLDEN_ANGLE * beats
            self._flash.hit(features.beat_strength * 0.5 + 0.5)

        bass = max(features.level("bass"), features.level("low mid") * 0.6)
        level = self._brightness.update(bass, tick.delta)
        flash = self._flash.update(0.0, tick.delta)
        brightness = self._shape(min(level * 0.75 + flash * 0.45, 1.0))

        # Warmer towards the treble end of the room, so it is not one flat wash.
        saturation = 1.0 - 0.25 * features.centroid
        for channel, x in self._positions.items():
            frame.set(channel, hsv(self._hue + x * 0.05, saturation), brightness)


@dataclass(slots=True)
class _Wave:
    hue: float
    strength: float
    position: float


class Sweep(Visual):
    """Every beat sends a wave of color travelling across the room.

    Waves overlap by taking whichever is brightest at a channel rather than
    adding up, so a fast passage stays colorful instead of washing out to white.

    Travel time and width matter more than they look. A busy track produces
    three to four onsets a second, so a wave has to clear the room in well under
    a second or the room simply stays lit and the beat stops reading at all.

    Both are relative to where the lamps actually are rather than to the full
    -1..1 axis. Entertainment areas are rarely centred - one here spans 0.3 to
    1.0 - and a wave crossing the whole axis would spend half its life in a part
    of the room with no lamps in it.
    """

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = DEFAULT_GAMMA,
        travel: float = 0.7,
        width: float = 0.25,
    ) -> None:
        super().__init__(positions, analyzer, gamma)
        span = self._positions.values()
        self._width = max((max(span) - min(span)) * width, 0.05)
        self._start = min(span) - self._width
        self._end = max(span) + self._width
        self._speed = (self._end - self._start) / travel
        self._waves: list[_Wave] = []
        self._hue = 0.0
        self._ambient = Envelope(0.05, 0.6)

    def paint(
        self, frame: Frame, tick: Tick, features: AudioFeatures, beats: int
    ) -> None:
        if beats:
            self._hue += GOLDEN_ANGLE * beats
            self._waves.append(
                _Wave(self._hue, 0.55 + 0.45 * features.beat_strength, self._start)
            )

        self._advance(tick.delta)
        ambient = self._ambient.update(features.energy * 0.12, tick.delta)
        base_hue = self._hue + 0.5

        for channel, x in self._positions.items():
            hue, level = base_hue, ambient
            for wave in self._waves:
                contribution = wave.strength * _falloff(x - wave.position, self._width)
                if contribution > level:
                    hue, level = wave.hue, contribution
            frame.set(
                channel, hsv(hue, 1.0 - 0.2 * features.centroid), self._shape(level)
            )

    def _advance(self, delta: float) -> None:
        for wave in self._waves:
            wave.position += self._speed * delta
        self._waves = [wave for wave in self._waves if wave.position <= self._end]


MODES: dict[str, type[Visual]] = {
    "spectrum": Spectrum,
    "pulse": Pulse,
    "sweep": Sweep,
}


def _mix(first: float, second: float, blend: float) -> float:
    return first + (second - first) * blend


def _falloff(distance: float, width: float) -> float:
    """A soft bell, so a wave fades in and out instead of jumping between lamps."""
    ratio = distance / width
    return max(1.0 - ratio * ratio, 0.0)


def mode_names() -> Sequence[str]:
    return tuple(MODES)
