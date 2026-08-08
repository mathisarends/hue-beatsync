import sys
from collections.abc import Iterable

_BLOCKS = " ▁▂▃▄▅▆▇█"
_ASCII_BLOCKS = " ....::||#"

_FILLED_CHARACTER, _EMPTY_CHARACTER = "█", "·"
_ASCII_FILLED, _ASCII_EMPTY = "#", "."


def _prepare_stdout() -> None:
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


_prepare_stdout()

_UNICODE = _drawable(_BLOCKS + _FILLED_CHARACTER + _EMPTY_CHARACTER)
_LEVELS = _BLOCKS if _UNICODE else _ASCII_BLOCKS
_FILLED = _FILLED_CHARACTER if _UNICODE else _ASCII_FILLED
_EMPTY = _EMPTY_CHARACTER if _UNICODE else _ASCII_EMPTY


def _block(level: float) -> str:
    index = round(_clamp(level) * (len(_LEVELS) - 1))
    return _LEVELS[index]


def bar(level: float, width: int = 10) -> str:
    filled = round(_clamp(level) * width)
    return _FILLED * filled + _EMPTY * (width - filled)


def sparkline(levels: Iterable[float]) -> str:
    return "".join(_block(level) for level in levels)


def _clamp(level: float) -> float:
    return min(max(level, 0.0), 1.0)
