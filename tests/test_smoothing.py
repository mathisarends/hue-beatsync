import pytest

from hue_beatsync.smoothing import Envelope, PeakFollower


def test_envelope_uses_attack_and_release_rates():
    envelope = Envelope(attack=0.01, release=1.0)

    rising = envelope.update(1.0, 0.1)
    falling = envelope.update(0.0, 0.1)

    assert rising > 0.99
    assert falling > 0.8


def test_envelope_hit_never_reduces_value():
    envelope = Envelope(value=0.8)

    envelope.hit(0.5)

    assert envelope.value == 0.8


def test_peak_follower_normalizes_against_decaying_peak():
    follower = PeakFollower(half_life=1.0)

    assert follower.normalize(2.0, 0.1) == 1.0
    assert follower.normalize(0.5, 1.0) == pytest.approx(0.5)
