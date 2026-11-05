import colorsys
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from hueify.color import RGB
from hueify.entertainment import Frame, Tick
from hueify.models import EntertainmentChannel

from lichtorgel.analysis import BAND_NAMES, AudioFeatures, SpectralAnalyzer
from lichtorgel.smoothing import Envelope

_BAND_HUES = (0.0, 0.08, 0.30, 0.52, 0.75)
_GOLDEN_ANGLE = 0.381966

_DEFAULT_GAMMA = 1.0
_DEFAULT_FLOOR = 0.18
_DEFAULT_LEAD = 0.1

_CALM_ENVELOPE = (0.12, 0.9)
_PUNCHY_ENVELOPE = (0.045, 0.35)
_FLASH_RELEASE = 0.22
_FLASH_GAIN = 0.85

_FULL_PUNCH_AT = 0.6
_PUNCH_STRETCH = 2.5
_PUNCH_SUSTAIN = 0.3
_PUNCH_FLOOR_DIP = 0.7

_HUE_TURNS_PER_SECOND = 0.35
_HUE_SNAP_PERCUSSIVENESS = 0.4

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
        lead: float = _DEFAULT_LEAD,
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
        self._beats = _BeatTrigger(analyzer, lead)

    def render(self, frame: Frame, tick: Tick) -> None:
        features = self._analyzer.features
        beat = self._beats.take(features)
        presence = _IDLE_PRESENCE if features.silent else 1.0
        self._presence.update(presence, tick.delta)
        self.paint(frame, tick, features, beat)

    def paint(
        self, frame: Frame, tick: Tick, features: AudioFeatures, beat: float | None
    ) -> None:
        """Paint one frame. ``beat`` is the strength of a beat to show in it."""
        raise NotImplementedError

    def _shape(self, level: float, punch: float = 0.0) -> float:
        """Map a 0 to 1 drive onto the part of a lamp's range that is visible.

        A Hue lamp stops being interesting well before zero, so a quiet passage
        driving 0.05 reads as off rather than as quiet. Lifting the whole range
        above a floor keeps it visible. The floor rides along with the presence
        envelope. Silence settles at a reduced presence instead of making a
        quiet bridge look as if the entertainment stream stopped.

        Punch lowers the floor again: a hit only reads as one when the room goes
        dark between hits, and the hits keep it from looking off.
        """
        shaped = min(max(level, 0.0), 1.0) ** self._gamma
        floor = self._floor * (1.0 - _PUNCH_FLOOR_DIP * punch)
        return (floor + (1.0 - floor) * shaped) * self._presence.value


class Spectrum(Visual):
    """Render an equalizer from bass on the left to treble on the right."""

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = _DEFAULT_GAMMA,
        floor: float = _DEFAULT_FLOOR,
        lead: float = _DEFAULT_LEAD,
    ) -> None:
        super().__init__(positions, analyzer, gamma, floor, lead)
        ordered = sorted(self._positions, key=lambda channel: self._positions[channel])
        span = max(len(ordered) - 1, 1)
        self._slots = {
            channel: index / span * (_BAND_COUNT - 1)
            for index, channel in enumerate(ordered)
        }
        self._envelopes = {channel: Envelope(*_CALM_ENVELOPE) for channel in ordered}

    def paint(
        self, frame: Frame, tick: Tick, features: AudioFeatures, beat: float | None
    ) -> None:
        for channel, slot in self._slots.items():
            lower = int(slot)
            upper = min(lower + 1, _BAND_COUNT - 1)
            blend = slot - lower

            level = _mix(features.levels[lower], features.levels[upper], blend)
            hue = _mix(_BAND_HUES[lower], _BAND_HUES[upper], blend)
            envelope = self._envelopes[channel]
            _tune(envelope, features.percussiveness)
            brightness = self._shape(
                envelope.update(level, tick.delta), _punch(features.percussiveness)
            )
            frame.set(channel, _hsv(hue), brightness_fraction=brightness)


class Pulse(Visual):
    """Pulse the room with bass and shift its hue on every beat."""

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = _DEFAULT_GAMMA,
        floor: float = _DEFAULT_FLOOR,
        lead: float = _DEFAULT_LEAD,
    ) -> None:
        super().__init__(positions, analyzer, gamma, floor, lead)
        self._brightness = Envelope(*_CALM_ENVELOPE)
        self._flash = Envelope(attack=0.0, release=_FLASH_RELEASE)
        self._spacing = _BeatSpacing()
        self._hue = _HueDrift()

    def paint(
        self, frame: Frame, tick: Tick, features: AudioFeatures, beat: float | None
    ) -> None:
        self._spacing.advance(tick.delta)
        # The lamps smooth every change on their own, and the bridge already
        # lags the music. A flash therefore lands at full strength in the frame
        # its beat arrives in, and only its decay is smoothed here.
        self._flash.update(0.0, tick.delta)
        punch = _punch(features.percussiveness)
        if beat is not None:
            self._change_hue(features.percussiveness)
            self._flash.hit((0.5 + 0.5 * beat) * punch * self._spacing.take())
        flash = self._flash.value

        _tune(self._brightness, features.percussiveness)
        bass = max(features.level("bass"), features.level("low mid") * 0.6)
        stretch = _mix(1.0, _PUNCH_STRETCH, punch)
        level = self._brightness.update(_stretch(bass, stretch), tick.delta)

        # With a beat to follow, the flash carries the kick and the sustained
        # level steps back, since a bassline keeps it up between kicks. Without
        # a beat, that sustained level is the whole show.
        sustain = _mix(0.95, _PUNCH_SUSTAIN, punch)
        brightness = self._shape(min(level * sustain + flash * _FLASH_GAIN, 1.0), punch)

        hue = self._hue.advance(tick.delta)
        saturation = 1.0 - 0.25 * features.centroid
        for channel, x in self._positions.items():
            frame.set(
                channel,
                _hsv(hue + x * 0.05, saturation),
                brightness_fraction=brightness,
            )

    def _change_hue(self, percussiveness: float) -> None:
        """Cut to the next color on a beat that hits, glide to it otherwise.

        A cut that lands with the flash reads as the beat changing the room. A
        glide lags the beat by most of a second, which only suits material that
        has no hit to land on.
        """
        if percussiveness >= _HUE_SNAP_PERCUSSIVENESS:
            self._hue.jump(_GOLDEN_ANGLE)
        else:
            self._hue.turn(_GOLDEN_ANGLE)


class Sweep(Visual):
    """Send a travelling wave across the room on every beat."""

    def __init__(
        self,
        positions: Mapping[int, float],
        analyzer: SpectralAnalyzer,
        gamma: float = _DEFAULT_GAMMA,
        floor: float = _DEFAULT_FLOOR,
        lead: float = _DEFAULT_LEAD,
        travel: float = 0.7,
        width: float = 0.25,
    ) -> None:
        super().__init__(positions, analyzer, gamma, floor, lead)
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
        self, frame: Frame, tick: Tick, features: AudioFeatures, beat: float | None
    ) -> None:
        self._spacing.advance(tick.delta)
        if beat is not None:
            if self._background.turn(_GOLDEN_ANGLE):
                self._hue = self._background.target
            strength = (0.55 + 0.45 * beat) * self._spacing.take()
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
                channel,
                _hsv(hue, 1.0 - 0.2 * features.centroid),
                brightness_fraction=self._shape(level, _punch(features.percussiveness)),
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
    lead: float = _DEFAULT_LEAD,
) -> Visual:
    """Create a visual by its public mode name."""
    try:
        visual_type = _VISUALS[name]
    except KeyError as error:
        choices = ", ".join(visual_names())
        raise ValueError(f"unknown visual {name!r}; choose from {choices}") from error
    return visual_type(positions, analyzer, gamma=gamma, floor=floor, lead=lead)


@dataclass(slots=True)
class _Wave:
    hue: float
    strength: float
    position: float


class _BeatTrigger:
    """Choose the frame each beat is shown in.

    While the analyzer trusts its beat grid, a beat fires ``lead`` seconds
    before it is due, which is how far the audio input, the bridge and the
    lamps together trail the frame that carries it. Without a grid, a beat
    fires when it is detected, which is as early as reacting gets.

    The prediction is refreshed with every audio block and wobbles by a few
    milliseconds, so a beat counts as already shown when one fired for a time
    less than half a period away.
    """

    __slots__ = ("_analyzer", "_lead", "_seen", "_shown")

    def __init__(self, analyzer: SpectralAnalyzer, lead: float) -> None:
        if lead < 0.0:
            raise ValueError("lead must not be negative")
        self._analyzer = analyzer
        self._lead = lead
        self._seen = analyzer.features.beats
        self._shown = -math.inf

    def take(self, features: AudioFeatures) -> float | None:
        """The strength of a beat to show in this frame, if there is one."""
        detected = features.beats != self._seen
        self._seen = features.beats
        now = self._analyzer.now()

        due = features.next_beat_at
        if due is None or features.bpm is None:
            if not detected:
                return None
            self._shown = now
            return features.beat_strength

        if now < due - self._lead or due - self._shown < 30.0 / features.bpm:
            return None
        self._shown = due
        return features.beat_confidence


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

    def jump(self, amount: float) -> None:
        self.target = (self.target + amount) % 1.0
        self.value = self.target

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


def _punch(percussiveness: float) -> float:
    """How hard to hit, from 0 for ambient material to 1 for a steady beat.

    Even a plain four-on-the-floor kick measures only around 0.55 percussive,
    so the full club look is reached there rather than at a value real music
    seldom gets to.
    """
    return min(percussiveness / _FULL_PUNCH_AT, 1.0)


def _stretch(level: float, factor: float) -> float:
    """Spend the lamp's range on only the loudest part of a level.

    Levels span a 42 dB window, which keeps quiet music visible but flattens a
    pump: a kick 6 dB above the bars between moves its level by a seventh.
    Stretching by 2.5 maps only the top 17 dB onto the lamp, so the same kick
    moves it by a third.
    """
    return max(1.0 - (1.0 - level) * factor, 0.0)


def _mix(first: float, second: float, blend: float) -> float:
    return first + (second - first) * blend


def _falloff(distance: float, width: float) -> float:
    ratio = distance / width
    return max(1.0 - ratio * ratio, 0.0)
