from pydantic import BaseModel, Field


class AudioSettings(BaseModel):
    """Where the sound comes from and how it is picked up."""

    device: int | str | None = None
    exclusive: bool | None = None
    gain: float | None = None


class AnalysisSettings(BaseModel):
    """How the signal is turned into loudness per frequency band."""

    sensitivity: float | None = None
    gamma: float | None = None
    floor: float | None = None
    max_frequency: float | None = None


class VisualSettings(BaseModel):
    """How the analysis is painted onto the lights."""

    mode: str | None = None
    rate: int | None = None


class SyncSettings(BaseModel):
    """Lichtorgel stream settings. Any field left unset falls back to a
    configured default (see /defaults), and then to the built-in default."""

    area: str | None = None
    audio: AudioSettings = Field(default_factory=AudioSettings)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)
    visual: VisualSettings = Field(default_factory=VisualSettings)


class ResolvedAudio(BaseModel):
    device: int | str | None = None
    exclusive: bool = False
    gain: float = 1.0


class ResolvedAnalysis(BaseModel):
    sensitivity: float = 1.2
    gamma: float = 1.0
    floor: float = 0.18
    max_frequency: float = 14_000.0


class ResolvedVisual(BaseModel):
    mode: str = "pulse"
    rate: int = 50


class ResolvedSettings(BaseModel):
    """SyncSettings with every field except `area` and `audio.device` filled
    in, i.e. the result of layering a request over configured defaults. The
    field defaults here are the built-in defaults, the bottom-most layer."""

    area: str | None = None
    audio: ResolvedAudio = Field(default_factory=ResolvedAudio)
    analysis: ResolvedAnalysis = Field(default_factory=ResolvedAnalysis)
    visual: ResolvedVisual = Field(default_factory=ResolvedVisual)


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
