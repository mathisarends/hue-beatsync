import sys
from collections.abc import Iterable

_BLOCKS = " ▁▂▃▄▅▆▇█"
_ASCII_BLOCKS = " ....::||#"


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

_LEVELS = _BLOCKS if _drawable(_BLOCKS) else _ASCII_BLOCKS


def _block(level: float) -> str:
    index = round(_clamp(level) * (len(_LEVELS) - 1))
    return _LEVELS[index]


def sparkline(levels: Iterable[float]) -> str:
    return "".join(_block(level) for level in levels)


def _clamp(level: float) -> float:
    return min(max(level, 0.0), 1.0)
