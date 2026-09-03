import asyncio

from hue_beatsync import BeatSync

from server.sync.base import SyncAlreadyRunning, SyncManager, SyncNotRunning


class BeatSyncManager(SyncManager):
    """Owns the single BeatSync stream this server is allowed to run."""

    def __init__(self) -> None:
        self._sync: BeatSync | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def area(self) -> str | None:
        return self._sync.area_name if self._sync else None

    async def start(self, area: str, **settings: object) -> None:
        if self.running:
            raise SyncAlreadyRunning(f"already streaming to {self.area!r}")
        sync = BeatSync(area, **settings)
        await sync.__aenter__()
        self._sync = sync
        self._task = asyncio.create_task(sync.run())

    async def stop(self) -> None:
        if not self.running or self._sync is None or self._task is None:
            raise SyncNotRunning("no sync is running")
        task, sync = self._task, self._sync
        self._task = None
        self._sync = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await sync.__aexit__(None, None, None)
