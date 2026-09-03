import asyncio
from typing import Protocol

from lichtorgel import Lichtorgel

from server.schemas import ResolvedSettings


class SyncAlreadyRunning(RuntimeError):
    pass


class SyncNotRunning(RuntimeError):
    pass


class SyncManager(Protocol):
    @property
    def running(self) -> bool: ...

    @property
    def area(self) -> str | None: ...

    async def start(self, settings: ResolvedSettings) -> None: ...

    async def stop(self) -> None: ...


class LichtorgelManager(SyncManager):
    """Owns the single Lichtorgel stream this server is allowed to run."""

    def __init__(self) -> None:
        self._lichtorgel: Lichtorgel | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def area(self) -> str | None:
        return self._lichtorgel.area_name if self._lichtorgel else None

    async def start(self, settings: ResolvedSettings) -> None:
        if self.running:
            raise SyncAlreadyRunning(f"already streaming to {self.area!r}")
        if settings.area is None:
            raise ValueError("area is required")
        lichtorgel = Lichtorgel(
            settings.area,
            device=settings.audio.device,
            mode=settings.visual.mode,
            rate=settings.visual.rate,
            sensitivity=settings.analysis.sensitivity,
            gamma=settings.analysis.gamma,
            floor=settings.analysis.floor,
            max_frequency=settings.analysis.max_frequency,
            exclusive=settings.audio.exclusive,
            gain=settings.audio.gain,
        )
        await lichtorgel.__aenter__()
        self._lichtorgel = lichtorgel
        self._task = asyncio.create_task(lichtorgel.run())

    async def stop(self) -> None:
        if not self.running or self._lichtorgel is None or self._task is None:
            raise SyncNotRunning("no sync is running")
        task, lichtorgel = self._task, self._lichtorgel
        self._task = None
        self._lichtorgel = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await lichtorgel.__aexit__(None, None, None)
