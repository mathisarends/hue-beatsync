from collections.abc import AsyncIterable

from dishka import Provider, Scope, make_async_container, provide

from server.defaults import DefaultsStore, YmlDefaultsStore
from server.discovery import Discovery, HueDiscovery
from server.sync import LichtorgelManager, SyncManager


class ManagerProvider(Provider):
    scope = Scope.APP

    @provide
    async def sync_manager(self) -> AsyncIterable[SyncManager]:
        manager = LichtorgelManager()
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
        return HueDiscovery()


container = make_async_container(ManagerProvider())
