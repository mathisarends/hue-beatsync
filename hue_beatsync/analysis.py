import math
import statistics
from collections import deque
from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from hue_beatsync.smoothing import Envelope, PeakFollower

BAND_NAMES = ("bass", "low mid", "mid", "high mid", "treble")

_LOWEST_FREQUENCY = 30.0
_HIGHEST_FREQUENCY = 14000.0


def band_edges(
    top: float = _HIGHEST_FREQUENCY, bottom: float = _LOWEST_FREQUENCY
) -> tuple[float, ...]:
    """Band boundaries spaced evenly on a log scale, which is how hearing works.

    ``top`` exists for microphones that cannot deliver the full range. A
    speakerphone is band limited to speech and carries nothing above roughly
    1600 Hz, so with the default edges its two top bands would sit at zero and
    the lamps driven by them would never light up. Squeezing all five bands into
    what the device actually hears uses every lamp again.
    """
    if not bottom < top:
        raise ValueError(f"The top frequency must be above {bottom} Hz, got {top}")
    ratio = (top / bottom) ** (1 / len(BAND_NAMES))
    return tuple(bottom * ratio**index for index in range(len(BAND_NAMES) + 1))


_BAND_EDGES = band_edges()

_WINDOW_SIZE = 2048
_FLUX_HISTORY = 128

_CENTROID_RANGE = (80.0, 6000.0)

_MIN_BEAT_GAP = 0.15
_SILENCE_RMS = 2e-3

_DEFAULT_SENSITIVITY = 1.2

_BAND_COUNT = len(BAND_NAMES)


@dataclass(frozen=True, slots=True)
class AudioFeatures:
    """An immutable analysis snapshot.

    ``beats`` is a cumulative counter so slower consumers do not miss onsets.
    """

    levels: tuple[float, ...]
    energy: float
    centroid: float
    beats: int
    beat_strength: float
    bpm: float | None
    loudness: float
    silent: bool

    def level(self, name: str) -> float:
        return self.levels[BAND_NAMES.index(name)]


_SILENCE = AudioFeatures(
    levels=(0.0,) * _BAND_COUNT,
    energy=0.0,
    centroid=0.5,
    beats=0,
    beat_strength=0.0,
    bpm=None,
    loudness=0.0,
    silent=True,
)


class SpectralAnalyzer:
    """Analyze audio blocks and expose the latest immutable snapshot."""

    def __init__(
        self,
        samplerate: int,
        window_size: int = _WINDOW_SIZE,
        sensitivity: float = _DEFAULT_SENSITIVITY,
        edges: tuple[float, ...] = _BAND_EDGES,
    ) -> None:
        if samplerate <= 0:
            raise ValueError("samplerate must be positive")
        if window_size <= 0:
            raise ValueError("window_size must be positive")
        if len(edges) != _BAND_COUNT + 1 or any(
            low >= high for low, high in pairwise(edges)
        ):
            raise ValueError(f"edges must contain {_BAND_COUNT + 1} increasing values")

        self._samplerate = samplerate
        self._window = np.hanning(window_size).astype(np.float32)
        self._buffer = np.zeros(window_size, dtype=np.float32)
        self._sensitivity = sensitivity
        self._edges = edges

        frequencies = np.fft.rfftfreq(window_size, 1 / samplerate)
        self._bands = _band_slices(frequencies, edges)
        self._log_frequencies = np.log(np.maximum(frequencies, 1.0))

        self._followers = [PeakFollower() for _ in range(_BAND_COUNT)]
        self._energy_follower = PeakFollower()
        self._centroid = Envelope(0.12, 0.12, value=0.5)
        self._previous_spectrum = np.zeros(len(frequencies), dtype=np.float32)
        self._flux_history: deque[float] = deque(maxlen=_FLUX_HISTORY)
        self._beat_times: deque[float] = deque(maxlen=12)

        self._features = _SILENCE
        self._elapsed = 0.0
        self._last_beat = -math.inf
        self._beats = 0

    @property
    def features(self) -> AudioFeatures:
        return self._features

    @property
    def bands(self) -> tuple[tuple[float, float], ...]:
        return tuple(pairwise(self._edges))

    def feed(self, block: np.ndarray, delta: float) -> None:
        self._elapsed += delta
        self._push(block)

        loudness = float(np.sqrt(np.mean(np.square(self._buffer))))
        if loudness < _SILENCE_RMS:
            self._decay(delta, loudness)
            return

        spectrum = np.abs(np.fft.rfft(self._buffer * self._window)).astype(np.float32)
        levels = self._band_levels(spectrum, delta)
        energy = self._energy_follower.normalize(float(spectrum.mean()), delta)
        strength = self._detect_beat(spectrum)

        self._features = AudioFeatures(
            levels=levels,
            energy=energy,
            centroid=self._centroid.update(
                _centroid_of(spectrum, self._log_frequencies), delta
            ),
            beats=self._beats,
            beat_strength=strength,
            bpm=self._bpm(),
            loudness=loudness,
            silent=False,
        )

    def _push(self, block: np.ndarray) -> None:
        size = len(self._buffer)
        if len(block) >= size:
            self._buffer = block[-size:].copy()
            return
        self._buffer = np.concatenate((self._buffer[len(block) :], block))

    def _band_levels(self, spectrum: np.ndarray, delta: float) -> tuple[float, ...]:
        return tuple(
            follower.normalize(float(spectrum[band].mean()), delta)
            for follower, band in zip(self._followers, self._bands, strict=True)
        )

    def _detect_beat(self, spectrum: np.ndarray) -> float:
        flux = float(np.sum(np.maximum(spectrum - self._previous_spectrum, 0.0)))
        self._previous_spectrum = spectrum

        history = self._flux_history
        history.append(flux)
        if len(history) < history.maxlen:
            return 0.0

        mean = statistics.fmean(history)
        threshold = mean + self._sensitivity * statistics.pstdev(history, mean)
        if flux <= threshold or self._elapsed - self._last_beat < _MIN_BEAT_GAP:
            return 0.0

        self._last_beat = self._elapsed
        self._beat_times.append(self._elapsed)
        self._beats += 1
        return min((flux - threshold) / max(threshold, 1e-6), 1.0)

    def _bpm(self) -> float | None:
        if len(self._beat_times) < 4:
            return None
        gaps = [
            second - first
            for first, second in pairwise(self._beat_times)
            if 0.25 <= second - first <= 1.2
        ]
        if len(gaps) < 3:
            return None
        return 60.0 / statistics.median(gaps)

    def _decay(self, delta: float, loudness: float) -> None:
        current = self._features
        fade = 0.5 ** (delta / 0.25)
        self._features = AudioFeatures(
            levels=tuple(level * fade for level in current.levels),
            energy=current.energy * fade,
            centroid=self._centroid.value,
            beats=self._beats,
            beat_strength=0.0,
            bpm=None,
            loudness=loudness,
            silent=True,
        )


def _centroid_of(spectrum: np.ndarray, log_frequencies: np.ndarray) -> float:
    total = float(spectrum.sum())
    if total <= 0.0:
        return 0.5
    center = float(np.dot(spectrum, log_frequencies) / total)
    low, high = (math.log(edge) for edge in _CENTROID_RANGE)
    return min(max((center - low) / (high - low), 0.0), 1.0)


def _band_slices(
    frequencies: np.ndarray, edges: tuple[float, ...]
) -> tuple[np.ndarray, ...]:
    slices = []
    for low, high in pairwise(edges):
        indices = np.flatnonzero((frequencies >= low) & (frequencies < high))
        if indices.size == 0:
            indices = np.array([int(np.argmin(np.abs(frequencies - low)))])
        slices.append(indices)
    return tuple(slices)
