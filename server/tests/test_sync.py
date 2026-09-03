import asyncio
from typing import Any, Self

import pytest

import server.sync as sync_module
from server.schemas import (
    ResolvedAnalysis,
    ResolvedAudio,
    ResolvedSettings,
    ResolvedVisual,
)
from server.sync import BeatSyncManager, SyncAlreadyRunning, SyncNotRunning


class FakeBeatSync:
    def __init__(self, area: str, **options: Any) -> None:
        self.area_name = area
        self.options = options
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> Self:
        self.entered = True
        return self

    async def __aexit__(self, *args: object) -> None:
        self.exited = True

    async def run(self) -> None:
        await asyncio.Event().wait()


@pytest.fixture
def beat_syncs(monkeypatch: pytest.MonkeyPatch) -> list[FakeBeatSync]:
    created: list[FakeBeatSync] = []

    def create(area: str, **options: Any) -> FakeBeatSync:
        sync = FakeBeatSync(area, **options)
        created.append(sync)
        return sync

    monkeypatch.setattr(sync_module, "BeatSync", create)
    return created


@pytest.mark.asyncio
async def test_start_forwards_resolved_settings_and_stop_cleans_up(
    beat_syncs: list[FakeBeatSync],
) -> None:
    settings = ResolvedSettings(
        area="Office",
        audio=ResolvedAudio(device=3, exclusive=True, gain=1.4),
        analysis=ResolvedAnalysis(
            sensitivity=1.5,
            gamma=0.9,
            floor=0.2,
            max_frequency=12_000,
        ),
        visual=ResolvedVisual(mode="sweep", rate=30),
    )
    manager = BeatSyncManager()

    await manager.start(settings)
    await asyncio.sleep(0)

    sync = beat_syncs[0]
    assert manager.running is True
    assert manager.area == "Office"
    assert sync.entered is True
    assert sync.options == {
        "device": 3,
        "mode": "sweep",
        "rate": 30,
        "sensitivity": 1.5,
        "gamma": 0.9,
        "floor": 0.2,
        "max_frequency": 12_000,
        "exclusive": True,
        "gain": 1.4,
    }

    await manager.stop()

    assert manager.running is False
    assert manager.area is None
    assert sync.exited is True


@pytest.mark.asyncio
async def test_start_rejects_missing_area(
    beat_syncs: list[FakeBeatSync],
) -> None:
    manager = BeatSyncManager()

    with pytest.raises(ValueError, match="area is required"):
        await manager.start(ResolvedSettings())

    assert beat_syncs == []


@pytest.mark.asyncio
async def test_start_rejects_a_second_running_sync(
    beat_syncs: list[FakeBeatSync],
) -> None:
    manager = BeatSyncManager()
    await manager.start(ResolvedSettings(area="Office"))

    with pytest.raises(SyncAlreadyRunning, match="Office"):
        await manager.start(ResolvedSettings(area="Kitchen"))

    assert len(beat_syncs) == 1
    await manager.stop()


@pytest.mark.asyncio
async def test_stop_rejects_when_no_sync_is_running() -> None:
    manager = BeatSyncManager()

    with pytest.raises(SyncNotRunning, match="no sync is running"):
        await manager.stop()
