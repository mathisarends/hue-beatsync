import math

import numpy as np

_WINDOW = 6.0
_MIN_HISTORY = 3.0
_UPDATE_INTERVAL = 0.1

_TEMPO_RANGE = (60.0, 180.0)
_TEMPO_PRIOR = 120.0
_TEMPO_PRIOR_OCTAVES = 1.0
_ONSET_BLUR = np.array([0.25, 0.5, 0.25])

_PHASE_DECAY = 0.8
_CAPTURE = 0.15
_PHASE_PULL = 0.3
_PERIOD_PULL = 0.2
_RELOCK_AFTER = 3
_CONFIDENCE_SMOOTHING = 0.3


class BeatTracker:
    """Follow the beat grid of the music, so a beat can be acted on before it lands.

    Reacting to an onset can never be early: by the time a kick is detected and
    the bridge has passed the frame on, the lamps trail the sound by a tenth of
    a second. Music keeps a steady pulse, though, so once its grid is known the
    next beat can be scheduled ahead of time by exactly that delay.

    The tempo comes from the autocorrelation of the onset envelope, weighted
    toward 120 BPM so a kick is not mistaken for its own half or double time.
    The phase comes from a comb over the most recent beats. Neither estimate is
    trusted on its own: the published grid is pulled toward each one and only
    jumps once several in a row agree that it is wrong, so a fill or a missing
    kick does not throw the lights off the beat.

    Confidence is how much stronger the beat is than its offbeat. A steady kick
    scores near one; sixteenth note hi-hats, which have as much onset on the
    offbeat as on the beat, score near zero.
    """

    def __init__(self, hop: float) -> None:
        if hop <= 0.0:
            raise ValueError("hop must be positive")
        self._hop = hop
        self._envelope = np.zeros(max(round(_WINDOW / hop), 8), dtype=np.float32)
        self._cursor = 0
        self._filled = 0
        self._elapsed = 0.0
        self._since_update = 0.0

        slowest, fastest = _TEMPO_RANGE
        self._lags = np.arange(
            max(math.floor(60.0 / fastest / hop), 1),
            math.ceil(60.0 / slowest / hop) + 1,
        )
        bpm = 60.0 / (self._lags * hop)
        self._prior = np.exp(
            -0.5 * (np.log2(bpm / _TEMPO_PRIOR) / _TEMPO_PRIOR_OCTAVES) ** 2
        )

        self._period: float | None = None
        self._anchor = 0.0
        self._disagreements = 0
        self._confidence = 0.0

    @property
    def period(self) -> float | None:
        """Seconds between beats, once a grid has been found."""
        return self._period

    @property
    def confidence(self) -> float:
        return self._confidence

    def push(self, onset: float, delta: float) -> None:
        """Add the onset strength of the hop that just ended."""
        self._elapsed += delta
        self._envelope[self._cursor] = onset
        self._cursor = (self._cursor + 1) % len(self._envelope)
        self._filled = min(self._filled + 1, len(self._envelope))

        self._since_update += delta
        if self._since_update < _UPDATE_INTERVAL:
            return
        self._since_update = 0.0
        if self._filled * self._hop >= _MIN_HISTORY:
            self._estimate()

    def until_next_beat(self) -> float | None:
        """Seconds from the latest hop to the next beat on the grid."""
        if self._period is None:
            return None
        since = (self._elapsed - self._anchor) % self._period
        return self._period - since

    def _estimate(self) -> None:
        envelope = self._recent()
        rises = np.maximum(envelope - envelope.mean(), 0.0)
        if not rises.any():
            self._confidence *= 1.0 - _CONFIDENCE_SMOOTHING
            return

        period = self._tempo(rises)
        offset, contrast = self._phase(rises, period / self._hop)
        self._follow(period, self._elapsed - offset * self._hop)
        self._confidence += (contrast - self._confidence) * _CONFIDENCE_SMOOTHING

    def _recent(self) -> np.ndarray:
        """The envelope in time order, oldest first."""
        if self._filled < len(self._envelope):
            return self._envelope[: self._filled].copy()
        return np.roll(self._envelope, -self._cursor)

    def _tempo(self, rises: np.ndarray) -> float:
        # A period that is not a whole number of hops puts its onsets alternately
        # one hop short and one hop long, and no single lag catches them all.
        # Blurring each onset over its neighbours lets the right lag collect both.
        rises = np.convolve(rises, _ONSET_BLUR, mode="same")
        size = len(rises)
        spectrum = np.fft.rfft(rises, 2 * size)
        correlation = np.fft.irfft(spectrum * np.conj(spectrum))[:size]
        lags = self._lags[self._lags < size - 1]
        best = int(lags[np.argmax(correlation[lags] * self._prior[: len(lags)])])
        return (best + _vertex(correlation, best)) * self._hop

    def _phase(self, rises: np.ndarray, frames: float) -> tuple[float, float]:
        """How many hops back the last beat was, and how clearly it stands out.

        Every candidate offset within one period is scored by the onsets that
        sit on a grid through it, recent beats counting most. The best offset is
        the beat; the one half a period away is its offbeat.
        """
        newest = len(rises) - 1
        offsets = np.arange(math.ceil(frames))
        beats = np.arange(max(int(newest // frames), 1))
        positions = np.rint(newest - offsets[:, None] - beats[None, :] * frames)
        valid = positions >= 0
        samples = rises[np.where(valid, positions, 0).astype(int)] * valid
        scores = samples @ (_PHASE_DECAY ** beats.astype(float))

        best = int(np.argmax(scores))
        peak = scores[best]
        if peak <= 0.0:
            return float(best), 0.0
        offbeat = scores[round(best + frames / 2) % len(scores)]
        # Noise has a best offset too, just not one that stands out from the
        # rest, so the beat has to beat both its offbeat and the average.
        contrast = min(1.0 - offbeat / peak, 1.0 - scores.mean() / peak)
        return float(best), float(contrast)

    def _follow(self, period: float, beat: float) -> None:
        """Pull the grid toward an estimate, or move it once estimates insist."""
        if self._period is None:
            self._lock(period, beat)
            return

        error = (beat - self._anchor + self._period / 2) % self._period
        error -= self._period / 2
        agrees = (
            abs(period - self._period) <= _CAPTURE * self._period
            and abs(error) <= _CAPTURE * self._period
        )
        if agrees:
            self._disagreements = 0
            self._period += (period - self._period) * _PERIOD_PULL
            self._anchor += error * _PHASE_PULL
            return

        self._disagreements += 1
        if self._disagreements >= _RELOCK_AFTER:
            self._lock(period, beat)

    def _lock(self, period: float, beat: float) -> None:
        self._period = period
        self._anchor = beat
        self._disagreements = 0


def _vertex(values: np.ndarray, index: int) -> float:
    """Where between its neighbours a sampled peak really lies, from -0.5 to 0.5."""
    if not 0 < index < len(values) - 1:
        return 0.0
    left, middle, right = values[index - 1], values[index], values[index + 1]
    curvature = left - 2.0 * middle + right
    if curvature >= 0.0:
        return 0.0
    return float(min(max(0.5 * (left - right) / curvature, -0.5), 0.5))
