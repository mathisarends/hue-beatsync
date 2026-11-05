import ctypes
import sys
from collections.abc import Iterator
from contextlib import contextmanager

_TIMER_PERIOD_MS = 1
_TIMERR_NOERROR = 0


@contextmanager
def fine_timer() -> Iterator[None]:
    """Run the block with a 1 ms system timer on Windows.

    Windows wakes sleeping threads on a 15.6 ms tick by default. The frame loop
    sleeps until the next 20 ms deadline, so frames left late by up to a whole
    tick: measured at 8.5 ms median and 17 ms worst case, which shows up as lights
    stuttering against the beat. Requesting a 1 ms period brings that to about
    1 ms. The request is process wide and undone on exit, and does nothing on
    other platforms, whose sleep is already precise.
    """
    if sys.platform != "win32":
        yield
        return

    winmm = ctypes.WinDLL("winmm")
    if winmm.timeBeginPeriod(_TIMER_PERIOD_MS) != _TIMERR_NOERROR:
        yield
        return
    try:
        yield
    finally:
        winmm.timeEndPeriod(_TIMER_PERIOD_MS)
