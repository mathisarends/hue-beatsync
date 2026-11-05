from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest
from hueify.entertainment import Frame

from lichtorgel.analysis import AudioFeatures, SpectralAnalyzer
from lichtorgel.visuals import (
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
    frame = fake_frame()
    analyzer._features = snapshot
    for _ in range(round(seconds / delta)):
        visual.render(frame, SimpleNamespace(delta=delta))
    return frame


def fake_frame():
    # Spec'd against the real Frame, so a call hueify no longer accepts fails here.
    return create_autospec(Frame, instance=True)


def brightnesses(frame):
    return [call.kwargs["brightness_fraction"] for call in frame.set.call_args_list]


def colors(frame):
    return [call.args[1] for call in frame.set.call_args_list]


@pytest.mark.parametrize("name", visual_names())
def test_visual_renders_each_channel(name, analyzer):
    visual = create_visual(name, {1: -1.0, 2: 1.0}, analyzer)
    analyzer._features = features()
    frame = fake_frame()

    visual.render(frame, SimpleNamespace(delta=0.02))

    assert frame.set.call_count == 2


@pytest.mark.parametrize("name", visual_names())
def test_quiet_audio_still_reaches_the_visible_range(name, analyzer):
    visual = create_visual(name, {1: 0.0}, analyzer, floor=0.2)

    quiet = features(levels=(0.02,) * 5, energy=0.02, percussiveness=0.0)

    frame = run(visual, analyzer, quiet, seconds=2.0)

    assert min(brightnesses(frame)[-5:]) >= 0.19


@pytest.mark.parametrize("name", visual_names())
def test_silence_settles_to_a_dim_visible_glow(name, analyzer):
    visual = create_visual(name, {1: 0.0}, analyzer, floor=0.2)
    run(visual, analyzer, features())
    silent = features(levels=(0.0,) * 5, energy=0.0, silent=True, percussiveness=0.0)

    frame = run(visual, analyzer, silent, seconds=8.0)

    assert 0.1 < brightnesses(frame)[-1] < 0.15


def test_pulse_eases_between_hues_on_calm_material(analyzer):
    visual = create_visual("pulse", {1: 0.0}, analyzer)
    run(visual, analyzer, features(beats=1, percussiveness=0.2), seconds=0.02)

    frame = run(visual, analyzer, features(beats=2, percussiveness=0.2), seconds=0.06)

    steps = colors(frame)
    assert len(set(steps)) > 1
    assert steps[0] != steps[-1]


def test_fast_beats_do_not_retarget_an_unfinished_hue_transition(analyzer):
    visual = create_visual("pulse", {1: 0.0}, analyzer)
    run(visual, analyzer, features(beats=1, percussiveness=0.2), seconds=0.02)
    target = visual._hue.target

    for beat in range(2, 8):
        run(visual, analyzer, features(beats=beat, percussiveness=0.2), seconds=0.1)

    assert visual._hue.target == target


def test_pulse_flashes_at_full_strength_in_the_beat_frame(analyzer):
    visual = create_visual("pulse", {1: 0.0}, analyzer, floor=0.0)
    quiet = features(levels=(0.0,) * 5, energy=0.0, beats=0)
    run(visual, analyzer, quiet, seconds=1.0)

    beat = features(
        levels=(0.0,) * 5,
        energy=0.0,
        beats=1,
        beat_strength=1.0,
        percussiveness=1.0,
    )
    frame = run(visual, analyzer, beat, seconds=0.02)

    assert brightnesses(frame)[0] == pytest.approx(0.85, abs=0.01)


def test_pulse_cuts_to_the_next_hue_on_a_beat_that_hits(analyzer):
    visual = create_visual("pulse", {1: 0.0}, analyzer)
    run(visual, analyzer, features(beats=1), seconds=0.02)

    frame = run(visual, analyzer, features(beats=2), seconds=0.06)

    steps = colors(frame)
    assert steps[0] == steps[-1]
    assert visual._hue.value == visual._hue.target


@pytest.mark.parametrize("name", visual_names())
def test_percussive_material_goes_darker_between_hits_than_ambient(name, analyzer):
    def resting_brightness(percussiveness):
        visual = create_visual(name, {1: 0.0}, analyzer, floor=0.2)
        between_hits = features(
            levels=(0.0,) * 5, energy=0.0, beats=0, percussiveness=percussiveness
        )
        return brightnesses(run(visual, analyzer, between_hits, seconds=2.0))[-1]

    assert resting_brightness(0.9) < resting_brightness(0.0) * 0.5


def test_pulse_pumps_a_steady_kick_against_a_sustained_bassline(analyzer):
    """The bassline keeps the bass band full; the kick still has to show."""
    visual = create_visual("pulse", {1: 0.0}, analyzer, floor=0.18)
    bassline = (0.4, 1.0, 0.5, 0.3, 0.2)
    measured = []
    for beat in range(1, 9):
        frame = run(
            visual,
            analyzer,
            features(levels=bassline, beats=beat, percussiveness=0.55),
            seconds=0.5,
        )
        measured = brightnesses(frame)

    assert max(measured) > 4 * min(measured)


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
            cycle(fake_frame())
        measured = fake_frame()
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
