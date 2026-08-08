from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self

import numpy as np

type BlockListener = Callable[[np.ndarray, float], None]


class AudioCapture(Protocol):
    """A source that pushes mono audio blocks to a configured listener."""

    @property
    def samplerate(self) -> int: ...

    @property
    def latency(self) -> float: ...

    @property
    def dropouts(self) -> int: ...

    @property
    def failure(self) -> BaseException | None: ...

    def start(self) -> Self: ...

    def stop(self) -> None: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...
