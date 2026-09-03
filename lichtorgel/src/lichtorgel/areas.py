from dataclasses import dataclass, replace

from hueify import Hueify
from hueify.models import EntertainmentConfiguration


@dataclass(frozen=True, slots=True)
class EntertainmentArea:
    id: str
    name: str
    active: bool
    channels: int


class AreaNotFoundError(ValueError):
    def __init__(self, wanted: str, areas: tuple[str, ...]) -> None:
        self.areas = areas
        known = ", ".join(areas) or "none"
        super().__init__(
            f"No entertainment area matches {wanted!r}. Available: {known}"
        )


async def list_areas() -> list[EntertainmentArea]:
    async with Hueify() as hue:
        response = await hue.entertainment.list()
    return sorted(
        (_area(configuration) for configuration in response.data),
        key=lambda area: (area.name.casefold(), area.name),
    )


async def stop_area(wanted: str) -> EntertainmentArea:
    if not wanted.strip():
        raise ValueError("area must not be empty")

    async with Hueify() as hue:
        response = await hue.entertainment.list()
        areas = [_area(configuration) for configuration in response.data]
        area = _find_area(wanted, areas)
        if area.active:
            await hue.entertainment.stop(area.id)
    return replace(area, active=False)


def _area(configuration: EntertainmentConfiguration) -> EntertainmentArea:
    return EntertainmentArea(
        id=str(configuration.id),
        name=configuration.name,
        active=configuration.is_streaming,
        channels=len(configuration.channels),
    )


def _find_area(wanted: str, areas: list[EntertainmentArea]) -> EntertainmentArea:
    normalized = wanted.strip().casefold()
    for area in areas:
        if area.id.casefold() == normalized or area.name.casefold() == normalized:
            return area
    names = tuple(sorted((area.name for area in areas), key=str.casefold))
    raise AreaNotFoundError(wanted, names)
