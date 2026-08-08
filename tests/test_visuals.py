from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hue_beatsync.analysis import AudioFeatures, SpectralAnalyzer
from hue_beatsync.visuals import (
    Pulse,
    Spectrum,
    Sweep,
    channel_positions,
    create_visual,
    visual_names,
)


@pytest.fixture
def analyzer():
    return SpectralAnalyzer(48_000, window_size=128)


@pytest.mark.parametrize(
    ("name", "expected"),
    [("spectrum", Spectrum), ("pulse", Pulse), ("sweep", Sweep)],
)
def test_create_visual(name, expected, analyzer):
    assert isinstance(create_visual(name, {1: -1.0, 2: 1.0}, analyzer), expected)


def test_visual_names_are_stable():
    assert visual_names() == ("spectrum", "pulse", "sweep")


def test_create_visual_rejects_unknown_name(analyzer):
    with pytest.raises(ValueError, match="unknown visual"):
        create_visual("missing", {1: 0.0}, analyzer)


def features(**overrides):
    defaults = {
        "levels": (0.8, 0.6, 0.4, 0.2, 0.1),
        "energy": 0.5,
        "centroid": 0.4,
        "beats": 1,
        "beat_strength": 0.8,
        "percussiveness": 0.9,
        "bpm": 120.0,
        "loudness": 0.3,
        "silent": False,
    }
    return AudioFeatures(**(defaults | overrides))


def run(visual, analyzer, snapshot, seconds=1.0, delta=0.02):
    frame = Mock()
    analyzer._features = snapshot
    for _ in range(round(seconds / delta)):
        visual.render(frame, SimpleNamespace(delta=delta))
    return frame


def brightnesses(frame):
    return [call.args[2] for call in frame.set.call_args_list]


def colors(frame):
    return [call.args[1] for call in frame.set.call_args_list]


@pytest.mark.parametrize("name", visual_names())
def test_visual_renders_each_channel(name, analyzer):
    visual = create_visual(name, {1: -1.0, 2: 1.0}, analyzer)
    analyzer._features = features()
    frame = Mock()

    visual.render(frame, SimpleNamespace(delta=0.02))

    assert frame.set.call_count == 2


@pytest.mark.parametrize("name", visual_names())
def test_quiet_audio_still_reaches_the_visible_range(name, analyzer):
    visual = create_visual(name, {1: 0.0}, analyzer, floor=0.2)

    quiet = features(levels=(0.02,) * 5, energy=0.02)

    frame = run(visual, analyzer, quiet, seconds=2.0)

    assert min(brightnesses(frame)[-5:]) >= 0.19


@pytest.mark.parametrize("name", visual_names())
def test_silence_fades_the_room_out(name, analyzer):
    visual = create_visual(name, {1: 0.0}, analyzer, floor=0.2)
    run(visual, analyzer, features())
    silent = features(levels=(0.0,) * 5, energy=0.0, silent=True)

    frame = run(visual, analyzer, silent, seconds=8.0)

    assert brightnesses(frame)[-1] < 0.02


def test_pulse_eases_between_hues_instead_of_jumping(analyzer):
    visual = create_visual("pulse", {1: 0.0}, analyzer)
    run(visual, analyzer, features(beats=1), seconds=0.02)

    frame = run(visual, analyzer, features(beats=2), seconds=0.06)

    steps = colors(frame)
    assert len(set(steps)) > 1
    assert steps[0] != steps[-1]


def test_crowded_beats_flash_weaker_than_spaced_ones(analyzer):
    """Sixteenth note filler must ripple, where a half second kick punches."""

    quiet = features(levels=(0.0,) * 5, energy=0.0)

    def peak_at(gap_seconds):
        visual = create_visual("pulse", {1: 0.0}, analyzer, floor=0.0)
        run(visual, analyzer, quiet, seconds=2.0)
        steps = max(round(gap_seconds / 0.02), 1)
        beat = 0

        def cycle(frame):
            nonlocal beat
            beat += 1
            for _ in range(steps):
                analyzer._features = features(levels=(0.0,) * 5, energy=0.0, beats=beat)
                visual.render(frame, SimpleNamespace(delta=0.02))

        for _ in range(5):
            cycle(Mock())
        measured = Mock()
        cycle(measured)
        return max(brightnesses(measured))

    assert peak_at(0.5) > peak_at(0.12) * 1.5


def test_visual_rejects_a_floor_outside_the_range(analyzer):
    with pytest.raises(ValueError, match="floor"):
        Pulse({1: 0.0}, analyzer, floor=1.0)


def test_channel_positions_uses_entertainment_geometry():
    channels = [
        SimpleNamespace(channel_id=3, position=SimpleNamespace(x=-0.5)),
        SimpleNamespace(channel_id=7, position=SimpleNamespace(x=0.75)),
    ]

    assert channel_positions(channels) == {3: -0.5, 7: 0.75}


@pytest.mark.parametrize("positions, gamma", [({}, 1.0), ({1: 0.0}, 0.0)])
def test_visual_rejects_invalid_configuration(positions, gamma, analyzer):
    with pytest.raises(ValueError):
        Pulse(positions, analyzer, gamma=gamma)


@pytest.mark.parametrize("travel, width", [(0.0, 0.25), (0.7, 0.0)])
def test_sweep_rejects_invalid_motion(travel, width, analyzer):
    with pytest.raises(ValueError):
        Sweep({1: 0.0}, analyzer, travel=travel, width=width)
