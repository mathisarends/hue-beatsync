from pydantic import BaseModel


class SyncSettings(BaseModel):
    """BeatSync stream settings. Any field left unset falls back to a
    configured default (see /defaults), and then to the built-in default."""

    area: str | None = None
    visual: str | None = None
    device: int | str | None = None
    rate: int | None = None
    sensitivity: float | None = None
    gamma: float | None = None
    floor: float | None = None
    max_frequency: float | None = None
    exclusive: bool | None = None
    gain: float | None = None


class ResolvedSettings(BaseModel):
    """SyncSettings with every field except `area` filled in, i.e. the
    result of layering a request over configured defaults. The field
    defaults here are the built-in defaults, the bottom-most layer."""

    area: str | None = None
    visual: str = "pulse"
    device: int | str | None = None
    rate: int = 50
    sensitivity: float = 1.2
    gamma: float = 1.0
    floor: float = 0.18
    max_frequency: float = 14_000.0
    exclusive: bool = False
    gain: float = 1.0


class AudioDeviceInfo(BaseModel):
    """An audio input, as accepted by the `device` setting (by `index`, or by
    any part of `name`)."""

    index: int
    name: str
    samplerate: int
    channels: int
    host_api: str
    is_default: bool
    supports_exclusive: bool


class AreaInfo(BaseModel):
    """A Hue entertainment area, as accepted by the `area` setting (by `id` or
    by `name`)."""

    id: str
    name: str
    active: bool
    channels: int


class StatusResponse(BaseModel):
    running: bool
    area: str | None = None
