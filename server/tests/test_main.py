import pytest

import server.main as main_module


def test_application_exposes_the_documented_routes() -> None:
    schema = main_module.app.openapi()

    assert schema["info"]["title"] == "hue-beatsync server"
    assert set(schema["paths"]) == {
        "/areas",
        "/defaults",
        "/devices",
        "/start",
        "/status",
        "/stop",
    }
    assert schema["paths"]["/start"]["post"]["operationId"] == "start_sync"


@pytest.mark.asyncio
async def test_lifespan_closes_the_dependency_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = False

    class FakeContainer:
        async def close(self) -> None:
            nonlocal closed
            closed = True

    monkeypatch.setattr(main_module, "container", FakeContainer())

    async with main_module.lifespan(main_module.app):
        assert closed is False

    assert closed is True
