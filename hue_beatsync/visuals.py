import colorsys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from hueify.color import RGB
from hueify.entertainment import Frame, Tick
from hueify.models import EntertainmentChannel

from hue_beatsync.analysis import BAND_NAMES, AudioFeatures, SpectralAnalyzer
from hue_beatsync.smoothing import Envelope

_BAND_HUES = (0.0, 0.08, 0.30, 0.52, 0.75)
_GOLDEN_ANGLE = 0.381966

_DEFAULT_GAMMA = 1.0

_BAND_COUNT = len(BAND_NAMES)


def channel_positions(channels: Iterable[EntertainmentChannel]) -> dict[int, float]:
    """Where each channel sits on the left to right axis, from -1 to 1."""
    return {channel.channel_id: channel.position.x for channel in channels}


class Visual:
    """Base class for audio-driven Hue frame sources."""

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = _DEFAULT_GAMMA,
    ) -> None:
        if not positions:
            raise ValueError("at least one channel position is required")
        if gamma <= 0:
            raise ValueError("gamma must be positive")
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
        return min(max(level, 0.0), 1.0) ** self._gamma


class Spectrum(Visual):
    """Render an equalizer from bass on the left to treble on the right."""

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = _DEFAULT_GAMMA,
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
            hue = _mix(_BAND_HUES[lower], _BAND_HUES[upper], blend)
            smoothed = self._envelopes[channel].update(level, tick.delta)
            frame.set(channel, _hsv(hue), self._shape(smoothed))


class Pulse(Visual):
    """Pulse the room with bass and shift its hue on every beat."""

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = _DEFAULT_GAMMA,
    ) -> None:
        super().__init__(positions, analyzer, gamma)
        self._brightness = Envelope(0.015, 0.22)
        self._flash = Envelope(0.005, 0.12)
        self._hue = 0.0

    def paint(
        self, frame: Frame, tick: Tick, features: AudioFeatures, beats: int
    ) -> None:
        if beats:
            self._hue += _GOLDEN_ANGLE * beats
            self._flash.hit(features.beat_strength * 0.5 + 0.5)

        bass = max(features.level("bass"), features.level("low mid") * 0.6)
        level = self._brightness.update(bass, tick.delta)
        flash = self._flash.update(0.0, tick.delta)
        brightness = self._shape(min(level * 0.75 + flash * 0.45, 1.0))

        saturation = 1.0 - 0.25 * features.centroid
        for channel, x in self._positions.items():
            frame.set(channel, _hsv(self._hue + x * 0.05, saturation), brightness)


class Sweep(Visual):
    """Send a travelling wave across the room on every beat."""

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = _DEFAULT_GAMMA,
        travel: float = 0.7,
        width: float = 0.25,
    ) -> None:
        super().__init__(positions, analyzer, gamma)
        if travel <= 0:
            raise ValueError("travel must be positive")
        if width <= 0:
            raise ValueError("width must be positive")
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
            self._hue += _GOLDEN_ANGLE * beats
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
                channel, _hsv(hue, 1.0 - 0.2 * features.centroid), self._shape(level)
            )

    def _advance(self, delta: float) -> None:
        for wave in self._waves:
            wave.position += self._speed * delta
        self._waves = [wave for wave in self._waves if wave.position <= self._end]


_VISUALS: dict[str, type[Visual]] = {
    "spectrum": Spectrum,
    "pulse": Pulse,
    "sweep": Sweep,
}


def visual_names() -> tuple[str, ...]:
    """Return the names accepted by :func:`create_visual`."""
    return tuple(_VISUALS)


def create_visual(
    name: str,
    positions: Mapping[int, float],
    analyzer: SpectralAnalyzer,
    *,
    gamma: float = _DEFAULT_GAMMA,
) -> Visual:
    """Create a visual by its public mode name."""
    try:
        visual_type = _VISUALS[name]
    except KeyError as error:
        choices = ", ".join(visual_names())
        raise ValueError(f"unknown visual {name!r}; choose from {choices}") from error
    return visual_type(positions, analyzer, gamma=gamma)


@dataclass(slots=True)
class _Wave:
    hue: float
    strength: float
    position: float


def _hsv(hue: float, saturation: float = 1.0, value: float = 1.0) -> RGB:
    red, green, blue = colorsys.hsv_to_rgb(hue % 1.0, saturation, value)
    return (round(red * 255), round(green * 255), round(blue * 255))


def _mix(first: float, second: float, blend: float) -> float:
    return first + (second - first) * blend


def _falloff(distance: float, width: float) -> float:
    ratio = distance / width
    return max(1.0 - ratio * ratio, 0.0)
