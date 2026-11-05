import pytest
from dishka import make_async_container

import hue_beatsync.server.dependencies as dependencies_module
from hue_beatsync.server.defaults import DefaultsStore, YmlDefaultsStore
from hue_beatsync.server.dependencies import ManagerProvider
from hue_beatsync.server.discovery import Discovery, HueDiscovery
from hue_beatsync.server.sync import BeatSyncManager, SyncManager


@pytest.mark.asyncio
async def test_provider_wires_production_adapters() -> None:
    container = make_async_container(ManagerProvider())

    try:
        manager = await container.get(SyncManager)
        defaults = await container.get(DefaultsStore)
        discovery = await container.get(Discovery)

        assert isinstance(manager, BeatSyncManager)
        assert isinstance(defaults, YmlDefaultsStore)
        assert isinstance(discovery, HueDiscovery)
    finally:
        await container.close()


@pytest.mark.asyncio
async def test_provider_stops_a_running_manager_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeManager:
        running = True
        stopped = False

        async def stop(self) -> None:
            self.running = False
            self.stopped = True

    manager = FakeManager()
    monkeypatch.setattr(dependencies_module, "BeatSyncManager", lambda: manager)
    container = make_async_container(ManagerProvider())

    resolved = await container.get(SyncManager)
    await container.close()

    assert resolved is manager
    assert manager.stopped is True
