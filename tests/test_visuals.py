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


@pytest.mark.parametrize("name", visual_names())
def test_visual_renders_each_channel(name, analyzer):
    visual = create_visual(name, {1: -1.0, 2: 1.0}, analyzer)
    analyzer._features = AudioFeatures(
        levels=(0.8, 0.6, 0.4, 0.2, 0.1),
        energy=0.5,
        centroid=0.4,
        beats=1,
        beat_strength=0.8,
        bpm=120.0,
        loudness=0.3,
        silent=False,
    )
    frame = Mock()

    visual.render(frame, SimpleNamespace(delta=0.02))

    assert frame.set.call_count == 2


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
