from pydantic import BaseModel


class StartRequest(BaseModel):
    area: str
    visual: str = "pulse"
    device: int | str | None = None
    rate: int = 50
    sensitivity: float = 1.2
    gamma: float = 1.0
    floor: float = 0.18
    max_frequency: float = 14_000.0
    exclusive: bool = False
    gain: float = 1.0


class StatusResponse(BaseModel):
    running: bool
    area: str | None = None
