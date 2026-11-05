import ctypes
import sys

import pytest

from lichtorgel.timing import fine_timer


class FakeWinmm:
    def __init__(self, begin_result: int = 0) -> None:
        self.begin_result = begin_result
        self.calls: list[tuple[str, int]] = []

    def timeBeginPeriod(self, period: int) -> int:
        self.calls.append(("begin", period))
        return self.begin_result

    def timeEndPeriod(self, period: int) -> int:
        self.calls.append(("end", period))
        return 0


@pytest.fixture
def winmm(monkeypatch):
    fake = FakeWinmm()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "WinDLL", lambda name: fake, raising=False)
    return fake


def test_fine_timer_requests_and_releases_a_1ms_period(winmm):
    with fine_timer():
        assert winmm.calls == [("begin", 1)]

    assert winmm.calls == [("begin", 1), ("end", 1)]


def test_fine_timer_releases_the_period_when_the_block_fails(winmm):
    with pytest.raises(RuntimeError), fine_timer():
        raise RuntimeError("stream failed")

    assert winmm.calls[-1] == ("end", 1)


def test_fine_timer_does_not_release_a_period_it_never_got(winmm):
    winmm.begin_result = 97  # TIMERR_NOCANDO

    with fine_timer():
        pass

    assert winmm.calls == [("begin", 1)]


def test_fine_timer_does_nothing_off_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        ctypes, "WinDLL", lambda name: pytest.fail("loaded winmm"), raising=False
    )

    with fine_timer():
        pass
