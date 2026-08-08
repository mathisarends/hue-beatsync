"""Turning raw audio into the handful of numbers a light show needs.

The chain is a short time Fourier transform, a split into frequency bands, and
an onset detector on top of the spectral flux. Everything is normalized against
what the room has recently been doing, so the result does not depend on how
loud the speakers are or how the track was mastered.
"""

from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from light_organ.smoothing import Envelope, PeakFollower

BAND_NAMES = ("bass", "low mid", "mid", "high mid", "treble")

LOWEST_FREQUENCY = 30.0
HIGHEST_FREQUENCY = 14000.0


def band_edges(
    top: float = HIGHEST_FREQUENCY, bottom: float = LOWEST_FREQUENCY
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


BAND_EDGES = band_edges()

WINDOW_SIZE = 2048
FLUX_HISTORY = 128

CENTROID_RANGE = (80.0, 6000.0)

MIN_BEAT_GAP = 0.15
SILENCE_RMS = 2e-3

# How many standard deviations above the recent average a flux peak has to be.
# Measured against a synthetic 120 BPM track: 1.2 catches 42 of 48 onsets,
# 1.5 drops to 34, and 2.0 keeps only the kicks.
DEFAULT_SENSITIVITY = 1.2

_BAND_COUNT = len(BAND_NAMES)


@dataclass(frozen=True, slots=True)
class AudioFeatures:
    """One snapshot of what the music is doing.

    ``beats`` counts every onset since the start instead of flagging the
    current block. The audio thread produces roughly 90 snapshots per second
    and the light stream reads 50, so a boolean would drop beats; a counter
    lets a reader see exactly how many it missed.
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


SILENCE = AudioFeatures(
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
    """Analyzes blocks on the audio thread and publishes the latest features.

    ``feed`` runs on PortAudio's thread while ``features`` is read from the
    event loop. No lock is needed because the only shared state is a single
    reference to a frozen snapshot, and rebinding it is atomic.
    """

    def __init__(
        self,
        samplerate: int,
        window_size: int = WINDOW_SIZE,
        sensitivity: float = DEFAULT_SENSITIVITY,
        edges: tuple[float, ...] = BAND_EDGES,
    ) -> None:
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
        # Symmetric, so this is a plain low pass: the raw centroid jumps across
        # its whole range between blocks, which would show up as color noise.
        self._centroid = Envelope(0.12, 0.12, value=0.5)
        self._previous_spectrum = np.zeros(len(frequencies), dtype=np.float32)
        self._flux_history: deque[float] = deque(maxlen=FLUX_HISTORY)
        self._beat_times: deque[float] = deque(maxlen=12)

        self._features = SILENCE
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
        if loudness < SILENCE_RMS:
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
        """Spectral flux against an adaptive threshold.

        Only rising bins count: a note starting is energy appearing across the
        spectrum at once, while a note fading out is not an onset.
        """
        flux = float(np.sum(np.maximum(spectrum - self._previous_spectrum, 0.0)))
        self._previous_spectrum = spectrum

        history = self._flux_history
        history.append(flux)
        if len(history) < history.maxlen:
            return 0.0

        mean = statistics.fmean(history)
        threshold = mean + self._sensitivity * statistics.pstdev(history, mean)
        if flux <= threshold or self._elapsed - self._last_beat < MIN_BEAT_GAP:
            return 0.0

        self._last_beat = self._elapsed
        self._beat_times.append(self._elapsed)
        self._beats += 1
        return min((flux - threshold) / max(threshold, 1e-6), 1.0)

    def _bpm(self) -> float | None:
        """A rough tempo from the gaps between onsets.

        Gaps outside 50..240 BPM are dropped rather than folded into the
        estimate: they are usually a missed beat or an extra percussive hit.
        """
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
    """Where the energy sits, on a log scale, as 0 (dark) to 1 (bright)."""
    total = float(spectrum.sum())
    if total <= 0.0:
        return 0.5
    center = float(np.dot(spectrum, log_frequencies) / total)
    low, high = (math.log(edge) for edge in CENTROID_RANGE)
    return min(max((center - low) / (high - low), 0.0), 1.0)


def _band_slices(
    frequencies: np.ndarray, edges: tuple[float, ...]
) -> tuple[np.ndarray, ...]:
    """Bin indices per band, with at least one bin each.

    The bass band is only a few bins wide at this window size, so an empty
    slice is a real risk and would make ``mean`` return NaN.
    """
    slices = []
    for low, high in pairwise(edges):
        indices = np.flatnonzero((frequencies >= low) & (frequencies < high))
        if indices.size == 0:
            indices = np.array([int(np.argmin(np.abs(frequencies - low)))])
        slices.append(indices)
    return tuple(slices)
