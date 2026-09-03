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


class StatusResponse(BaseModel):
    running: bool
    area: str | None = None
