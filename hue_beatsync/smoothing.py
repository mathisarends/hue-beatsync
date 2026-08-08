import math


class Envelope:
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
        self.value = max(self.value, value)


class PeakFollower:
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
