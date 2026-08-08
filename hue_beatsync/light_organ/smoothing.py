"""Time based smoothers, so the lights glide instead of flicker.

Every smoother takes the elapsed time as an argument rather than assuming a
fixed update rate. The audio thread runs at roughly 90 updates per second and
the light stream at 50, and both should feel the same.
"""

import math


class Envelope:
    """A value that snaps towards a rising target and falls back slowly.

    ``attack`` and ``release`` are the seconds it takes to cover about two
    thirds of the distance to a new target. Short attack and long release is
    what makes a beat read as a hit instead of a wobble.
    """

    __slots__ = ("_attack", "_release", "value")

    def __init__(
        self, attack: float = 0.01, release: float = 0.25, value: float = 0.0
    ) -> None:
        self._attack = attack
        self._release = release
        self.value = value

    def update(self, target: float, delta: float) -> float:
        constant = self._attack if target > self.value else self._release
        self.value += (target - self.value) * _weight(constant, delta)
        return self.value

    def hit(self, value: float = 1.0) -> None:
        """Jump straight up, for the frame a beat lands on."""
        self.value = max(self.value, value)


class PeakFollower:
    """The recent loudest value, decaying towards silence.

    Dividing a level by its peak turns absolute microphone amplitudes into a
    0..1 range that follows how loud the room actually is. Without it every
    mapping would depend on the recording volume, the distance to the speakers
    and how the track was mastered.
    """

    __slots__ = ("_floor", "_half_life", "peak")

    def __init__(self, half_life: float = 2.0, floor: float = 1e-4) -> None:
        self._half_life = half_life
        self._floor = floor
        self.peak = floor

    def normalize(self, value: float, delta: float) -> float:
        decayed = self.peak * 0.5 ** (delta / self._half_life)
        self.peak = max(value, decayed, self._floor)
        return min(value / self.peak, 1.0)


def _weight(constant: float, delta: float) -> float:
    if constant <= 0.0:
        return 1.0
    return 1.0 - math.exp(-delta / constant)
