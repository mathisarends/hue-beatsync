import numpy as np
import pytest

from hue_beatsync.analysis import AudioFeatures, SpectralAnalyzer, band_edges


def test_band_edges_are_logarithmic():
    edges = band_edges(top=960.0, bottom=30.0)
    ratios = [high / low for low, high in zip(edges[:-1], edges[1:], strict=True)]

    assert len(edges) == 6
    assert ratios == pytest.approx([2.0] * 5)


def test_band_edges_reject_invalid_range():
    with pytest.raises(ValueError, match="top frequency"):
        band_edges(top=30.0, bottom=30.0)


@pytest.mark.parametrize("samplerate, window_size", [(0, 128), (48_000, 0)])
def test_analyzer_rejects_invalid_dimensions(samplerate, window_size):
    with pytest.raises(ValueError):
        SpectralAnalyzer(samplerate, window_size=window_size)


def test_analyzer_rejects_malformed_band_edges():
    with pytest.raises(ValueError, match="6 increasing values"):
        SpectralAnalyzer(48_000, edges=(30.0, 100.0))


def test_silent_input_publishes_silent_features():
    analyzer = SpectralAnalyzer(48_000, window_size=128)

    analyzer.feed(np.zeros(64, dtype=np.float32), delta=64 / 48_000)

    assert analyzer.features.silent is True
    assert analyzer.features.loudness == 0.0
    assert analyzer.features.levels == (0.0,) * 5


def test_tone_publishes_normalized_features():
    rate = 48_000
    size = 2_048
    time = np.arange(size) / rate
    tone = np.sin(2 * np.pi * 440 * time).astype(np.float32) * 0.5
    analyzer = SpectralAnalyzer(rate, window_size=size)

    analyzer.feed(tone, delta=size / rate)

    features = analyzer.features
    assert features.silent is False
    assert 0.0 <= features.energy <= 1.0
    assert all(0.0 <= level <= 1.0 for level in features.levels)
    assert features.level("mid") > features.level("treble")


def test_audio_features_resolves_named_level():
    features = AudioFeatures((1, 2, 3, 4, 5), 0, 0, 0, 0, None, 0, False)

    assert features.level("high mid") == 4
