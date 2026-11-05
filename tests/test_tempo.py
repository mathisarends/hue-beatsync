import numpy as np
import pytest

from hue_beatsync.tempo import BeatTracker

HOP = 512 / 48_000


def pulses(seconds, interval, start=0.2, skip=()):
    """An onset envelope with a sharp onset every ``interval`` seconds."""
    envelope = np.zeros(round(seconds / HOP))
    for index, onset in enumerate(np.arange(start, seconds, interval)):
        if index not in skip:
            envelope[round(onset / HOP)] = 1.0
    return envelope


def track(*envelopes):
    tracker = BeatTracker(HOP)
    for envelope in envelopes:
        for onset in envelope:
            tracker.push(float(onset), HOP)
    return tracker


def time_to_next(seconds, interval, start=0.2):
    """When the next pulse is due after ``seconds`` of the train have elapsed."""
    passed = (seconds - start) % interval
    return interval - passed


def phase_error(tracker, seconds, interval, start=0.2):
    error = tracker.until_next_beat() - time_to_next(seconds, interval, start)
    return (error + interval / 2) % interval - interval / 2


def test_tracker_has_no_grid_before_it_has_heard_enough():
    tracker = track(pulses(2.0, 0.5))

    assert tracker.period is None
    assert tracker.until_next_beat() is None


@pytest.mark.parametrize("bpm", [90.0, 120.0, 128.0, 150.0, 174.0])
def test_tracker_locks_to_the_tempo_and_phase_of_a_steady_beat(bpm):
    interval = 60.0 / bpm
    envelope = pulses(10.0, interval)

    tracker = track(envelope)

    assert 60.0 / tracker.period == pytest.approx(bpm, abs=1.0)
    assert abs(phase_error(tracker, len(envelope) * HOP, interval)) < 2 * HOP
    assert tracker.confidence > 0.8


def test_tracker_does_not_trust_onsets_without_a_pulse():
    noise = np.random.default_rng(0).random(round(10.0 / HOP))

    tracker = track(noise)

    assert tracker.confidence < 0.6


def test_tracker_keeps_the_grid_through_a_missing_kick():
    steady = pulses(8.0, 0.5)
    gap = pulses(2.0, 0.5, start=0.2, skip=(1,))
    tracker = track(steady)
    period = tracker.period

    tracker = track(steady, gap)

    assert tracker.period == pytest.approx(period, rel=0.02)
    elapsed = (len(steady) + len(gap)) * HOP
    assert abs(phase_error(tracker, elapsed, 0.5)) < 2 * HOP


def test_tracker_moves_to_a_new_tempo():
    before = pulses(8.0, 0.5)
    after = pulses(6.0, 60.0 / 140.0)

    tracker = track(before, after)

    assert 60.0 / tracker.period == pytest.approx(140.0, abs=1.5)


def test_tracker_rejects_a_hop_that_is_not_positive():
    with pytest.raises(ValueError, match="hop"):
        BeatTracker(0.0)
