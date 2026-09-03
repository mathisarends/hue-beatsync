from abc import ABC, abstractmethod

from server.schemas import AreaInfo, AudioDeviceInfo


class DiscoveryUnavailable(RuntimeError):
    """The audio backend or the Hue bridge could not be reached."""


class Discovery(ABC):
    """Lists what a caller can actually pick for `area` and `device`.

    Both settings are free-form on the way in - an area name or id, a device
    index or name fragment - so a client needs a way to see the valid choices
    before calling /start.
    """

    @abstractmethod
    async def devices(self) -> list[AudioDeviceInfo]: ...

    @abstractmethod
    async def areas(self) -> list[AreaInfo]: ...
