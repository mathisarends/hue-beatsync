"""Terminal output that survives a Windows console.

Python picks cp1252 for stdout on a German Windows install, which cannot encode
block characters at all. Switching the stream to UTF-8 is only half the fix -
the console still has to be able to draw them - so every bar has an ASCII
fallback that is chosen once, at import time.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable

BLOCKS = " ▁▂▃▄▅▆▇█"
ASCII_BLOCKS = " ....::||#"

FILLED, EMPTY = "█", "·"
ASCII_FILLED, ASCII_EMPTY = "#", "."


def prepare_stdout() -> None:
    """Give stdout the best encoding it will accept."""
    with_utf8 = getattr(sys.stdout, "reconfigure", None)
    if with_utf8 is not None:
        with_utf8(encoding="utf-8", errors="replace")


def _drawable(text: str) -> bool:
    encoding = sys.stdout.encoding or "ascii"
    try:
        text.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


prepare_stdout()

_UNICODE = _drawable(BLOCKS + FILLED + EMPTY)
_LEVELS = BLOCKS if _UNICODE else ASCII_BLOCKS
_FILLED = FILLED if _UNICODE else ASCII_FILLED
_EMPTY = EMPTY if _UNICODE else ASCII_EMPTY


def block(level: float) -> str:
    """One character standing for a level between 0 and 1."""
    index = round(_clamp(level) * (len(_LEVELS) - 1))
    return _LEVELS[index]


def bar(level: float, width: int = 10) -> str:
    filled = round(_clamp(level) * width)
    return _FILLED * filled + _EMPTY * (width - filled)


def sparkline(levels: Iterable[float]) -> str:
    return "".join(block(level) for level in levels)


def _clamp(level: float) -> float:
    return min(max(level, 0.0), 1.0)
