from abc import ABC, abstractmethod
from typing import Any

from server.schemas import SyncSettings


class DefaultsStore(ABC):
    """Configured BeatSync defaults.

    Layered under a request's explicit fields and over the built-in
    defaults, so a user can configure e.g. their usual area/sensitivity
    once and only pass overrides to /start afterwards.
    """

    @property
    @abstractmethod
    def current(self) -> SyncSettings: ...

    @abstractmethod
    def update(self, changes: SyncSettings) -> SyncSettings: ...

    @abstractmethod
    def resolve(self, request: SyncSettings) -> dict[str, Any]: ...
