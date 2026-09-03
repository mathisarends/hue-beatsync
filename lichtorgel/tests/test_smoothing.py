import pytest

from lichtorgel.smoothing import Envelope, PeakFollower


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
    assert follower.peak == pytest.approx(2.0)
    assert follower.normalize(1.0, 1.0) == 1.0


def test_peak_follower_keeps_quiet_material_visible():
    follower = PeakFollower(half_life=1.0, range_db=40.0)
    follower.normalize(1.0, 0.1)

    twenty_db_down = follower.normalize(0.1, 0.0)

    assert twenty_db_down == pytest.approx(0.5)


@pytest.mark.parametrize("value", [0.0, -1.0])
def test_peak_follower_reports_no_level_without_signal(value):
    assert PeakFollower().normalize(value, 0.1) == 0.0


def test_peak_follower_bottoms_out_below_its_range():
    follower = PeakFollower(half_life=100.0, range_db=20.0)
    follower.normalize(1.0, 0.1)

    assert follower.normalize(1e-6, 0.1) == 0.0


@pytest.mark.parametrize("half_life, range_db", [(0.0, 40.0), (1.0, 0.0)])
def test_peak_follower_rejects_invalid_scales(half_life, range_db):
    with pytest.raises(ValueError):
        PeakFollower(half_life=half_life, range_db=range_db)
