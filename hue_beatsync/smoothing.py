import math

_DEFAULT_HALF_LIFE = 6.0
_DEFAULT_RANGE_DB = 42.0
_QUIETEST = 1e-9


class Envelope:
    __slots__ = ("attack", "release", "value")

    def __init__(
        self, attack: float = 0.01, release: float = 0.25, value: float = 0.0
    ) -> None:
        self.attack = attack
        self.release = release
        self.value = value

    def update(self, target: float, delta: float) -> float:
        constant = self.attack if target > self.value else self.release
        self.value += (target - self.value) * _weight(constant, delta)
        return self.value

    def hit(self, value: float = 1.0) -> None:
        self.value = max(self.value, value)


class PeakFollower:
    """Normalize magnitudes against a decaying peak, on a decibel scale.

    A plain ratio to the peak spends almost its entire range on the loudest few
    decibels. Material 20 dB down - clearly audible, an ordinary quiet passage -
    lands at 0.1 and the lamp it drives reads as off. Mapping the ratio onto a
    fixed decibel window instead tracks how loud a passage actually sounds, so
    quiet music stays visible without erasing the difference to loud music.
    """

    __slots__ = ("_floor", "_half_life", "_range_db", "peak")

    def __init__(
        self,
        half_life: float = _DEFAULT_HALF_LIFE,
        floor: float = 1e-4,
        range_db: float = _DEFAULT_RANGE_DB,
    ) -> None:
        if half_life <= 0.0:
            raise ValueError("half_life must be positive")
        if range_db <= 0.0:
            raise ValueError("range_db must be positive")
        self._half_life = half_life
        self._floor = floor
        self._range_db = range_db
        self.peak = floor

    def normalize(self, value: float, delta: float) -> float:
        decayed = self.peak * 0.5 ** (delta / self._half_life)
        self.peak = max(value, decayed, self._floor)
        if value <= 0.0:
            return 0.0
        decibels = 20.0 * math.log10(max(value / self.peak, _QUIETEST))
        return min(max(1.0 + decibels / self._range_db, 0.0), 1.0)


def _weight(constant: float, delta: float) -> float:
    if constant <= 0.0:
        return 1.0
    return 1.0 - math.exp(-delta / constant)
