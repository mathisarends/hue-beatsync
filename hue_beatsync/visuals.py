import colorsys
import math
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
_DEFAULT_FLOOR = 0.18

_CALM_ENVELOPE = (0.12, 0.9)
_PUNCHY_ENVELOPE = (0.045, 0.35)
_FLASH_ENVELOPE = (0.04, 0.2)

_HUE_TURNS_PER_SECOND = 0.35

_PRESENCE_FADE = (0.15, 1.2)
_IDLE_PRESENCE = 0.65

_BOUNCE_GAP = 0.45

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
        floor: float = _DEFAULT_FLOOR,
    ) -> None:
        if not positions:
            raise ValueError("at least one channel position is required")
        if gamma <= 0:
            raise ValueError("gamma must be positive")
        if not 0.0 <= floor < 1.0:
            raise ValueError("floor must be at least 0 and below 1")
        self._positions = dict(positions)
        self._analyzer = analyzer
        self._gamma = gamma
        self._floor = floor
        self._presence = Envelope(*_PRESENCE_FADE)
        self._seen_beats = analyzer.features.beats

    def render(self, frame: Frame, tick: Tick) -> None:
        features = self._analyzer.features
        beats = features.beats - self._seen_beats
        self._seen_beats = features.beats
        presence = _IDLE_PRESENCE if features.silent else 1.0
        self._presence.update(presence, tick.delta)
        self.paint(frame, tick, features, beats)

    def paint(
        self, frame: Frame, tick: Tick, features: AudioFeatures, beats: int
    ) -> None:
        raise NotImplementedError

    def _shape(self, level: float) -> float:
        """Map a 0 to 1 drive onto the part of a lamp's range that is visible.

        A Hue lamp stops being interesting well before zero, so a quiet passage
        driving 0.05 reads as off rather than as quiet. Lifting the whole range
        above a floor keeps it visible. The floor rides along with the presence
        envelope. Silence settles at a reduced presence instead of making a
        quiet bridge look as if the entertainment stream stopped.
        """
        shaped = min(max(level, 0.0), 1.0) ** self._gamma
        return (self._floor + (1.0 - self._floor) * shaped) * self._presence.value


class Spectrum(Visual):
    """Render an equalizer from bass on the left to treble on the right."""

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = _DEFAULT_GAMMA,
        floor: float = _DEFAULT_FLOOR,
    ) -> None:
        super().__init__(positions, analyzer, gamma, floor)
        ordered = sorted(self._positions, key=lambda channel: self._positions[channel])
        span = max(len(ordered) - 1, 1)
        self._slots = {
            channel: index / span * (_BAND_COUNT - 1)
            for index, channel in enumerate(ordered)
        }
        self._envelopes = {channel: Envelope(*_CALM_ENVELOPE) for channel in ordered}

    def paint(
        self, frame: Frame, tick: Tick, features: AudioFeatures, beats: int
    ) -> None:
        for channel, slot in self._slots.items():
            lower = int(slot)
            upper = min(lower + 1, _BAND_COUNT - 1)
            blend = slot - lower

            level = _mix(features.levels[lower], features.levels[upper], blend)
            hue = _mix(_BAND_HUES[lower], _BAND_HUES[upper], blend)
            envelope = self._envelopes[channel]
            _tune(envelope, features.percussiveness)
            frame.set(
                channel, _hsv(hue), self._shape(envelope.update(level, tick.delta))
            )


class Pulse(Visual):
    """Pulse the room with bass and shift its hue on every beat."""

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = _DEFAULT_GAMMA,
        floor: float = _DEFAULT_FLOOR,
    ) -> None:
        super().__init__(positions, analyzer, gamma, floor)
        self._brightness = Envelope(*_CALM_ENVELOPE)
        self._flash = Envelope(*_FLASH_ENVELOPE)
        self._spacing = _BeatSpacing()
        self._hue = _HueDrift()

    def paint(
        self, frame: Frame, tick: Tick, features: AudioFeatures, beats: int
    ) -> None:
        self._spacing.advance(tick.delta)
        flash_target = 0.0
        if beats:
            self._hue.turn(_GOLDEN_ANGLE)
            flash_target = (
                (0.5 + 0.5 * features.beat_strength)
                * features.percussiveness
                * self._spacing.take()
            )

        _tune(self._brightness, features.percussiveness)
        bass = max(features.level("bass"), features.level("low mid") * 0.6)
        level = self._brightness.update(bass, tick.delta)
        flash = self._flash.update(flash_target, tick.delta)

        # Percussive material needs headroom above the sustained level for the
        # flash to land in; without beats that headroom is only lost brightness.
        sustain = _mix(0.95, 0.7, features.percussiveness)
        brightness = self._shape(min(level * sustain + flash * 0.45, 1.0))

        hue = self._hue.advance(tick.delta)
        saturation = 1.0 - 0.25 * features.centroid
        for channel, x in self._positions.items():
            frame.set(channel, _hsv(hue + x * 0.05, saturation), brightness)


class Sweep(Visual):
    """Send a travelling wave across the room on every beat."""

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = _DEFAULT_GAMMA,
        floor: float = _DEFAULT_FLOOR,
        travel: float = 0.7,
        width: float = 0.25,
    ) -> None:
        super().__init__(positions, analyzer, gamma, floor)
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
        self._background = _HueDrift()
        self._spacing = _BeatSpacing()
        self._ambient = Envelope(*_CALM_ENVELOPE)

    def paint(
        self, frame: Frame, tick: Tick, features: AudioFeatures, beats: int
    ) -> None:
        self._spacing.advance(tick.delta)
        if beats:
            if self._background.turn(_GOLDEN_ANGLE):
                self._hue = self._background.target
            strength = (0.55 + 0.45 * features.beat_strength) * self._spacing.take()
            self._waves.append(_Wave(self._hue, strength, self._start))

        self._advance(tick.delta)

        # With no waves to contrast against, the background carries the whole
        # show and has to be bright enough to be one.
        glow = _mix(0.75, 0.15, features.percussiveness)
        _tune(self._ambient, features.percussiveness)
        ambient = self._ambient.update(features.energy * glow, tick.delta)
        base_hue = self._background.advance(tick.delta) + 0.5

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
    floor: float = _DEFAULT_FLOOR,
) -> Visual:
    """Create a visual by its public mode name."""
    try:
        visual_type = _VISUALS[name]
    except KeyError as error:
        choices = ", ".join(visual_names())
        raise ValueError(f"unknown visual {name!r}; choose from {choices}") from error
    return visual_type(positions, analyzer, gamma=gamma, floor=floor)


@dataclass(slots=True)
class _Wave:
    hue: float
    strength: float
    position: float


class _BeatSpacing:
    """How much room the beat that just landed had to itself, from 0 to 1.

    A kick every half second should hit at full strength. A sixteenth note
    hi-hat pattern arriving four times a second should not, or the room strobes
    on filler even though every one of those onsets is real. Scaling by the gap
    keeps the groove intact and turns the rest into a ripple.
    """

    __slots__ = ("_elapsed",)

    def __init__(self) -> None:
        self._elapsed = _BOUNCE_GAP

    def advance(self, delta: float) -> None:
        self._elapsed += delta

    def take(self) -> float:
        room = min(self._elapsed / _BOUNCE_GAP, 1.0)
        self._elapsed = 0.0
        return room


class _HueDrift:
    """Travel toward a target hue the short way around the wheel.

    Jumping the hue on every beat is what makes a fast passage look like a
    strobe rather than like a light show. Moving at a bounded rate keeps the
    same colors in the same order, but arrives at them as a sweep.
    """

    __slots__ = ("_rate", "target", "value")

    def __init__(self, rate: float = _HUE_TURNS_PER_SECOND) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        self._rate = rate
        self.value = 0.0
        self.target = 0.0

    def turn(self, amount: float) -> bool:
        if self.value != self.target:
            return False
        self.target = (self.target + amount) % 1.0
        return True

    def advance(self, delta: float) -> float:
        distance = (self.target - self.value + 0.5) % 1.0 - 0.5
        step = self._rate * delta
        if abs(distance) <= step:
            self.value = self.target
        else:
            self.value = (self.value + math.copysign(step, distance)) % 1.0
        return self.value


def _tune(envelope: Envelope, percussiveness: float) -> None:
    """Follow the music only as fast as it deserves.

    A short attack is what makes a kick land, but on ambient material the same
    setting turns spectral noise into visible flicker. Interpolating the
    constants with how percussive the material is serves both.
    """
    calm_attack, calm_release = _CALM_ENVELOPE
    punchy_attack, punchy_release = _PUNCHY_ENVELOPE
    envelope.attack = _mix(calm_attack, punchy_attack, percussiveness)
    envelope.release = _mix(calm_release, punchy_release, percussiveness)


def _hsv(hue: float, saturation: float = 1.0, value: float = 1.0) -> RGB:
    red, green, blue = colorsys.hsv_to_rgb(hue % 1.0, saturation, value)
    return (round(red * 255), round(green * 255), round(blue * 255))


def _mix(first: float, second: float, blend: float) -> float:
    return first + (second - first) * blend


def _falloff(distance: float, width: float) -> float:
    ratio = distance / width
    return max(1.0 - ratio * ratio, 0.0)
