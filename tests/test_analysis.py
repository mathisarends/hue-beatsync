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
    features = AudioFeatures((1, 2, 3, 4, 5), 0, 0, 0, 0, 0, None, 0, False)

    assert features.level("high mid") == 4


def _feed(analyzer, samples, rate=48_000, block=512):
    for start in range(0, len(samples) - block, block):
        analyzer.feed(samples[start : start + block], delta=block / rate)


def _pad(rate, seconds, amplitude=0.2, seed=0):
    """Sustained chord over a little noise, the shape of ambient material."""
    generator = np.random.default_rng(seed)
    time = np.arange(int(rate * seconds)) / rate
    chord = sum(np.sin(2 * np.pi * partial * time) for partial in (110.0, 220.0, 660.0))
    noise = generator.standard_normal(len(time)) * 0.1
    return ((chord / 3 + noise) * amplitude).astype(np.float32)


def _beats(rate, seconds, interval=0.5, amplitude=0.2, seed=0):
    """The same material with a kick drum on top of it."""
    samples = _pad(rate, seconds, amplitude, seed)
    time = np.arange(int(rate * 0.12)) / rate
    kick = (np.sin(2 * np.pi * 60 * time) * np.exp(-time / 0.03)).astype(np.float32)
    for onset in np.arange(0.4, seconds - 0.2, interval):
        start = int(onset * rate)
        samples[start : start + len(kick)] += kick
    return samples


def _claps(rate, seconds, interval=1.0, amplitude=0.2, seed=3):
    """A backbeat carried by claps, with no kick drum anywhere in it."""
    samples = _pad(rate, seconds, amplitude, seed)
    generator = np.random.default_rng(seed)
    time = np.arange(int(rate * 0.2)) / rate
    body = np.sin(2 * np.pi * 200 * time) * 0.5
    clap = (body + generator.standard_normal(len(time)) * 0.8) * np.exp(-time / 0.035)
    for onset in np.arange(0.75, seconds - 0.3, interval):
        start = int(onset * rate)
        samples[start : start + len(clap)] += clap.astype(np.float32)
    return samples


def _hats(rate, seconds, interval=0.125, amplitude=0.15, seed=4):
    """Sixteenth note hi-hats, the filler that should not drive the room."""
    samples = _pad(rate, seconds, amplitude, seed)
    generator = np.random.default_rng(seed)
    time = np.arange(int(rate * 0.04)) / rate
    noise = generator.standard_normal(len(time))
    noise[1:] -= noise[:-1]
    hat = (noise * np.exp(-time / 0.006) * 0.5).astype(np.float32)
    for onset in np.arange(0.4, seconds - 0.2, interval):
        start = int(onset * rate)
        samples[start : start + len(hat)] += hat
    return samples


def test_ambient_material_does_not_produce_beats():
    rate = 48_000
    analyzer = SpectralAnalyzer(rate)

    _feed(analyzer, _pad(rate, 6.0), rate)

    assert analyzer.features.beats == 0
    assert analyzer.features.percussiveness < 0.15


def test_a_kick_drum_produces_beats():
    rate = 48_000
    analyzer = SpectralAnalyzer(rate)

    _feed(analyzer, _beats(rate, 8.0), rate)

    features = analyzer.features
    assert features.beats >= 6
    assert features.percussiveness > 0.15
    assert features.bpm == pytest.approx(120.0, abs=15.0)


def test_a_backbeat_of_claps_produces_beats_without_any_kick():
    rate = 48_000
    analyzer = SpectralAnalyzer(rate)

    _feed(analyzer, _claps(rate, 8.0), rate)

    features = analyzer.features
    assert features.beats >= 5
    assert features.percussiveness > 0.5
    assert features.bpm is not None


def test_fast_hi_hats_do_not_drive_the_room_at_their_own_rate():
    """Sixteenths at 480 onsets per minute must not become 480 light changes."""
    rate = 48_000
    analyzer = SpectralAnalyzer(rate)

    _feed(analyzer, _hats(rate, 8.0), rate)

    assert analyzer.features.beats <= 2
    assert analyzer.features.bpm is None


def test_a_quiet_passage_after_a_loud_one_stays_visible():
    rate = 48_000
    analyzer = SpectralAnalyzer(rate)
    _feed(analyzer, _pad(rate, 2.0, amplitude=0.3), rate)

    _feed(analyzer, _pad(rate, 0.4, amplitude=0.03), rate)

    assert analyzer.features.silent is False
    assert analyzer.features.level("low mid") > 0.4


def test_quiet_music_is_not_mistaken_for_silence():
    rate = 48_000
    analyzer = SpectralAnalyzer(rate)

    _feed(analyzer, _pad(rate, 1.0, amplitude=0.006), rate)

    assert analyzer.features.silent is False


def test_a_short_gap_in_the_music_does_not_count_as_silence():
    """A breakdown or a beat of nothing must not drop the room to dark."""
    rate = 48_000
    analyzer = SpectralAnalyzer(rate)
    _feed(analyzer, _beats(rate, 3.0, amplitude=0.25), rate)

    _feed(analyzer, np.zeros(int(rate * 0.8), dtype=np.float32), rate)

    assert analyzer.features.silent is False


def test_sustained_silence_is_reported():
    rate = 48_000
    analyzer = SpectralAnalyzer(rate)
    _feed(analyzer, _beats(rate, 3.0, amplitude=0.25), rate)

    _feed(analyzer, np.zeros(int(rate * 3.0), dtype=np.float32), rate)

    assert analyzer.features.silent is True
