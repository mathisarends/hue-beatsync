import math
import statistics
from collections import deque
from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from lichtorgel.smoothing import Envelope, PeakFollower

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
    return _log_edges(len(BAND_NAMES), bottom, top)


def _log_edges(count: int, bottom: float, top: float) -> tuple[float, ...]:
    ratio = (top / bottom) ** (1 / count)
    return tuple(bottom * ratio**index for index in range(count + 1))


_BAND_EDGES = band_edges()

_WINDOW_SIZE = 2048
_FLUX_HISTORY = 128

_CENTROID_RANGE = (80.0, 6000.0)

_MIN_BEAT_GAP = 0.26
_ONSET_BANDS = 24
_ONSET_RANGE = (40.0, 12000.0)
_ONSET_LOBES = (
    (70.0, 0.9, 0.45),
    (200.0, 0.8, 0.8),
    (2000.0, 0.75, 1.25),
)
_ONSET_BASE_WEIGHT = 0.03
_ONSET_FLOOR_RATIO = 1e-3
_DRUM_BODY_RANGES = ((40.0, 500.0), (500.0, 4000.0))
_CYMBAL_RANGE = (5000.0, 12000.0)
_MIN_DRUM_PROMINENCE = 3.65
_FLUX_MARGIN = 0.4
_CREST_RANGE = (0.85, 1.60)
_MIN_PERCUSSIVENESS = 0.15
_PERCUSSIVENESS_SETTLING = 1.5
_TEMPO_RANGE = (0.25, 1.2)

_SILENCE_RMS = 8e-4
_SILENCE_HYSTERESIS = 1.25
_SILENCE_HOLD = 1.5

_DEFAULT_SENSITIVITY = 1.2

_BAND_COUNT = len(BAND_NAMES)


@dataclass(frozen=True, slots=True)
class AudioFeatures:
    """An immutable analysis snapshot.

    ``beats`` is a cumulative counter so slower consumers do not miss onsets.
    ``percussiveness`` says how much of a beat there is to follow at all, which
    lets a visual stay calm on material that has none.
    """

    levels: tuple[float, ...]
    energy: float
    centroid: float
    beats: int
    beat_strength: float
    percussiveness: float
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
    percussiveness=0.0,
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
        self._edges = edges

        frequencies = np.fft.rfftfreq(window_size, 1 / samplerate)
        self._bands = _band_slices(frequencies, edges)
        self._log_frequencies = np.log(np.maximum(frequencies, 1.0))

        self._followers = [PeakFollower() for _ in range(_BAND_COUNT)]
        self._energy_follower = PeakFollower()
        self._centroid = Envelope(0.12, 0.12, value=0.5)
        self._onsets = _OnsetDetector(sensitivity, frequencies)

        self._features = _SILENCE
        self._elapsed = 0.0
        # Starting settled, so a stream that opens on silence does not spend the
        # hold amplifying the noise floor into a full brightness light show.
        self._quiet_for = _SILENCE_HOLD

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
        if self._is_silent(loudness, delta):
            self._decay(delta, loudness)
            return

        spectrum = np.abs(np.fft.rfft(self._buffer * self._window)).astype(np.float32)
        levels = self._band_levels(spectrum, delta)
        energy = self._energy_follower.normalize(float(spectrum.mean()), delta)
        strength = self._onsets.feed(spectrum, self._elapsed, delta)

        self._features = AudioFeatures(
            levels=levels,
            energy=energy,
            centroid=self._centroid.update(
                _centroid_of(spectrum, self._log_frequencies), delta
            ),
            beats=self._onsets.beats,
            beat_strength=strength,
            percussiveness=self._onsets.percussiveness,
            bpm=self._onsets.bpm(),
            loudness=loudness,
            silent=False,
        )

    def _is_silent(self, loudness: float, delta: float) -> bool:
        """Whether the input has been below the gate long enough to count.

        A gate that reacts the moment it is crossed turns every breakdown, fade
        and quiet bar into a dark room. Audio therefore has to stay below the
        gate for a while before the lights give up on it, and needs to clear it
        by only a small margin to bring them straight back. Making the return
        expensive instead would strand a quiet input below the gate for good.
        """
        gate = _SILENCE_RMS * (_SILENCE_HYSTERESIS if self._features.silent else 1.0)
        if loudness >= gate:
            self._quiet_for = 0.0
            return False
        self._quiet_for += delta
        return self._quiet_for >= _SILENCE_HOLD

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

    def _decay(self, delta: float, loudness: float) -> None:
        current = self._features
        fade = 0.5 ** (delta / 0.25)
        self._features = AudioFeatures(
            levels=tuple(level * fade for level in current.levels),
            energy=current.energy * fade,
            centroid=self._centroid.value,
            beats=self._onsets.beats,
            beat_strength=0.0,
            percussiveness=self._onsets.settle(delta),
            bpm=None,
            loudness=loudness,
            silent=True,
        )


class _OnsetDetector:
    """Spectral flux onset detection with a gate for material that has no beat.

    Thresholding flux at "the recent mean plus a few standard deviations" alone
    fires constantly on ambient music: with little variance in the history every
    ripple clears the threshold, and the lights end up strobing on noise.

    Three things fix that. The spectrum is folded into a few dozen log spaced
    bands before anything is differenced, because summing raw bins adds up a
    thousand independent noise fluctuations and buries the one drum that matters
    under them. The rise is then measured on log magnitudes, so a band doubling
    counts the same whether the track is loud or quiet. And how peaked the
    resulting flux is - its crest - is published as ``percussiveness``, both to
    suppress beats on material that has none and to let visuals slow themselves
    down when there is nothing to hit.
    """

    def __init__(self, sensitivity: float, frequencies: np.ndarray) -> None:
        low, high = _ONSET_RANGE
        edges = _log_edges(_ONSET_BANDS, low, high)
        self._sensitivity = sensitivity
        self._bands = _band_slices(frequencies, edges)
        self._weights = _onset_weights(edges)
        self._drum_body = tuple(
            np.flatnonzero((frequencies >= low) & (frequencies < high))
            for low, high in _DRUM_BODY_RANGES
        )
        low, high = _CYMBAL_RANGE
        self._cymbals = np.flatnonzero((frequencies >= low) & (frequencies < high))
        self._previous = np.zeros(_ONSET_BANDS, dtype=np.float32)
        self._history: deque[float] = deque(maxlen=_FLUX_HISTORY)
        self._beat_times: deque[float] = deque(maxlen=12)
        self._percussiveness = Envelope(
            _PERCUSSIVENESS_SETTLING, _PERCUSSIVENESS_SETTLING
        )
        self._last_beat = -math.inf
        self._beats = 0

    @property
    def beats(self) -> int:
        return self._beats

    @property
    def percussiveness(self) -> float:
        return self._percussiveness.value

    def feed(self, spectrum: np.ndarray, elapsed: float, delta: float) -> float:
        """Consume one spectrum and return the strength of any onset in it."""
        flux = self._flux(spectrum)
        history = self._history
        history.append(flux)
        if len(history) < history.maxlen:
            return 0.0
        if self._drum_prominence(spectrum) < _MIN_DRUM_PROMINENCE:
            self._percussiveness.update(0.0, delta)
            return 0.0

        mean = statistics.fmean(history)
        deviation = statistics.pstdev(history, mean)
        percussiveness = self._percussiveness.update(
            _crest_to_percussiveness(deviation, mean), delta
        )
        if percussiveness < _MIN_PERCUSSIVENESS:
            return 0.0

        threshold = max(
            mean + self._sensitivity * deviation, mean * (1.0 + _FLUX_MARGIN)
        )
        if flux <= threshold or elapsed - self._last_beat < _MIN_BEAT_GAP:
            return 0.0

        self._last_beat = elapsed
        self._beat_times.append(elapsed)
        self._beats += 1
        return min((flux - threshold) / max(threshold, 1e-6), 1.0)

    def settle(self, delta: float) -> float:
        """Relax toward "no beat here" while the input is silent."""
        return self._percussiveness.update(0.0, delta)

    def bpm(self) -> float | None:
        if len(self._beat_times) < 4:
            return None
        shortest, longest = _TEMPO_RANGE
        gaps = [
            second - first
            for first, second in pairwise(self._beat_times)
            if shortest <= second - first <= longest
        ]
        if len(gaps) < 3:
            return None
        return 60.0 / statistics.median(gaps)

    def _flux(self, spectrum: np.ndarray) -> float:
        bands = np.array(
            [spectrum[band].mean() for band in self._bands], dtype=np.float32
        )
        # Bands far below the loudest one hold nothing but noise, whose log
        # swings wildly for no audible reason.
        floor = max(float(bands.max()) * _ONSET_FLOOR_RATIO, 1e-9)
        compressed = np.log(np.maximum(bands, floor))
        rise = np.maximum(compressed - self._previous, 0.0)
        self._previous = compressed
        return float(np.dot(rise, self._weights))

    def _drum_prominence(self, spectrum: np.ndarray) -> float:
        body = sum(float(spectrum[band].mean()) for band in self._drum_body)
        cymbals = float(spectrum[self._cymbals].mean())
        return body / max(cymbals, 1e-9)


def _onset_weights(edges: tuple[float, ...]) -> np.ndarray:
    """Weight the flux toward the drums a listener hears as the rhythm.

    The dominant lobes cover the body around 200 Hz and the crack around 2 kHz
    that distinguish a snare or clap from broadband cymbal noise. A smaller
    supporting lobe keeps the kick around 70 Hz. Frequencies outside these
    regions receive very little weight, so a sixteenth-note hi-hat pattern does
    not drive the lights instead of the groove.
    """
    centers = np.sqrt(np.array(edges[:-1]) * np.array(edges[1:]))
    weights = np.full(len(centers), _ONSET_BASE_WEIGHT)
    for center, width, gain in _ONSET_LOBES:
        weights += gain * np.exp(-0.5 * (np.log2(centers / center) / width) ** 2)
    return weights.astype(np.float32)


def _crest_to_percussiveness(deviation: float, mean: float) -> float:
    if mean <= 0.0:
        return 0.0
    low, high = _CREST_RANGE
    return min(max((deviation / mean - low) / (high - low), 0.0), 1.0)


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
