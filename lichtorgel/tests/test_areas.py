from types import SimpleNamespace
from uuid import UUID

import pytest

from lichtorgel import areas
from lichtorgel.areas import AreaNotFoundError, EntertainmentArea


class Entertainment:
    def __init__(self, configurations):
        self.configurations = configurations
        self.stopped = []

    async def list(self):
        return SimpleNamespace(data=self.configurations)

    async def stop(self, area_id):
        self.stopped.append(area_id)


class Hue:
    def __init__(self, entertainment):
        self.entertainment = entertainment

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        pass


def configuration(name, *, active=False, channels=2):
    return SimpleNamespace(
        id=UUID(int=len(name)),
        name=name,
        is_streaming=active,
        channels=[object()] * channels,
    )


async def test_list_areas_returns_stable_product_models(monkeypatch):
    entertainment = Entertainment(
        [configuration("Studio", active=True), configuration("Music", channels=4)]
    )
    monkeypatch.setattr(areas, "Hueify", lambda: Hue(entertainment))

    result = await areas.list_areas()

    assert result == [
        EntertainmentArea(str(UUID(int=5)), "Music", False, 4),
        EntertainmentArea(str(UUID(int=6)), "Studio", True, 2),
    ]


async def test_stop_area_releases_active_area(monkeypatch):
    configuration_ = configuration("Studio", active=True)
    entertainment = Entertainment([configuration_])
    monkeypatch.setattr(areas, "Hueify", lambda: Hue(entertainment))

    stopped = await areas.stop_area("studio")

    assert stopped.active is False
    assert entertainment.stopped == [str(configuration_.id)]


async def test_stop_area_is_idempotent(monkeypatch):
    entertainment = Entertainment([configuration("Studio")])
    monkeypatch.setattr(areas, "Hueify", lambda: Hue(entertainment))

    await areas.stop_area("Studio")

    assert entertainment.stopped == []


async def test_unknown_area_lists_available_names(monkeypatch):
    entertainment = Entertainment([configuration("Studio"), configuration("Music")])
    monkeypatch.setattr(areas, "Hueify", lambda: Hue(entertainment))

    with pytest.raises(AreaNotFoundError) as caught:
        await areas.stop_area("Kitchen")

    assert caught.value.areas == ("Music", "Studio")
