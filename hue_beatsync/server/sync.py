import asyncio
from typing import Protocol

from hue_beatsync import BeatSync
from hue_beatsync.server.schemas import ResolvedSettings


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


class BeatSyncManager(SyncManager):
    """Owns the single BeatSync stream this server is allowed to run."""

    def __init__(self) -> None:
        self._beatsync: BeatSync | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def area(self) -> str | None:
        return self._beatsync.area_name if self._beatsync else None

    async def start(self, settings: ResolvedSettings) -> None:
        if self.running:
            raise SyncAlreadyRunning(f"already streaming to {self.area!r}")
        if settings.area is None:
            raise ValueError("area is required")
        beatsync = BeatSync(
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
        await beatsync.__aenter__()
        self._beatsync = beatsync
        self._task = asyncio.create_task(beatsync.run())

    async def stop(self) -> None:
        if not self.running or self._beatsync is None or self._task is None:
            raise SyncNotRunning("no sync is running")
        task, beatsync = self._task, self._beatsync
        self._task = None
        self._beatsync = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await beatsync.__aexit__(None, None, None)
