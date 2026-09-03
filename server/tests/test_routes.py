import pytest

from server.routes import start
from server.schemas import ResolvedSettings, StatusResponse, SyncSettings


class FakeDefaultsStore:
    def __init__(self, resolved: ResolvedSettings) -> None:
        self.resolved = resolved

    def resolve(self, request: SyncSettings) -> ResolvedSettings:
        return self.resolved

    @property
    def current(self) -> SyncSettings:
        return SyncSettings()

    def update(self, changes: SyncSettings) -> SyncSettings:
        return changes


class FakeSyncManager:
    def __init__(self) -> None:
        self.settings: ResolvedSettings | None = None

    @property
    def running(self) -> bool:
        return self.settings is not None

    @property
    def area(self) -> str | None:
        return self.settings.area if self.settings else None

    async def start(self, settings: ResolvedSettings) -> None:
        self.settings = settings

    async def stop(self) -> None:
        self.settings = None


@pytest.mark.asyncio
async def test_start_uses_resolved_settings() -> None:
    settings = ResolvedSettings(area="Office")
    manager = FakeSyncManager()

    response = await start(
        SyncSettings(),
        manager,
        FakeDefaultsStore(settings),
    )

    assert manager.settings is settings
    assert response == StatusResponse(running=True, area="Office")
