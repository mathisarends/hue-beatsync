from abc import ABC, abstractmethod


class SyncAlreadyRunning(RuntimeError):
    pass


class SyncNotRunning(RuntimeError):
    pass


class SyncManager(ABC):
    """Owns the single BeatSync stream a server implementation is allowed to run."""

    @property
    @abstractmethod
    def running(self) -> bool: ...

    @property
    @abstractmethod
    def area(self) -> str | None: ...

    @abstractmethod
    async def start(self, area: str, **settings: object) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...
