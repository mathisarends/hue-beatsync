from collections.abc import AsyncIterable

from dishka import Provider, Scope, make_async_container, provide

from server.configuration import DefaultsStore, YmlDefaultsStore
from server.discovery import Discovery, HueBeatSyncDiscovery
from server.sync import BeatSyncManager, SyncManager


class ManagerProvider(Provider):
    scope = Scope.APP

    @provide
    async def sync_manager(self) -> AsyncIterable[SyncManager]:
        manager = BeatSyncManager()
        try:
            yield manager
        finally:
            if manager.running:
                await manager.stop()

    @provide
    def defaults_store(self) -> DefaultsStore:
        return YmlDefaultsStore()

    @provide
    def discovery(self) -> Discovery:
        return HueBeatSyncDiscovery()


container = make_async_container(ManagerProvider())
