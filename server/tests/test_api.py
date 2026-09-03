import asyncio
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.defaults import DefaultsStore
from server.discovery import Discovery, DiscoveryUnavailable
from server.routes import router
from server.schemas import (
    AreaInfo,
    AudioDeviceInfo,
    ResolvedSettings,
    SyncSettings,
)
from server.sync import SyncAlreadyRunning, SyncManager, SyncNotRunning


class FakeDefaultsStore:
    def __init__(self) -> None:
        self.current = SyncSettings(area="Living Room")
        self.resolved = ResolvedSettings(area="Living Room")
        self.last_request: SyncSettings | None = None

    def update(self, changes: SyncSettings) -> SyncSettings:
        self.current = changes
        return self.current

    def resolve(self, request: SyncSettings) -> ResolvedSettings:
        self.last_request = request
        return self.resolved


class FakeDiscovery:
    def __init__(self) -> None:
        self.error: DiscoveryUnavailable | None = None
        self.available_devices = [
            AudioDeviceInfo(
                index=3,
                name="Speakers (loopback)",
                samplerate=48_000,
                channels=2,
                host_api="Windows WASAPI",
                is_default=True,
                supports_exclusive=True,
            )
        ]
        self.available_areas = [
            AreaInfo(id="area-1", name="Living Room", active=False, channels=3)
        ]

    async def devices(self) -> list[AudioDeviceInfo]:
        if self.error:
            raise self.error
        return self.available_devices

    async def areas(self) -> list[AreaInfo]:
        if self.error:
            raise self.error
        return self.available_areas


class FakeSyncManager:
    def __init__(self) -> None:
        self.running = False
        self.area: str | None = None
        self.settings: ResolvedSettings | None = None
        self.start_error: Exception | None = None
        self.stop_error: Exception | None = None

    async def start(self, settings: ResolvedSettings) -> None:
        if self.start_error:
            raise self.start_error
        self.settings = settings
        self.running = True
        self.area = settings.area

    async def stop(self) -> None:
        if self.stop_error:
            raise self.stop_error
        self.running = False
        self.area = None


class FakeProvider(Provider):
    scope = Scope.APP

    def __init__(
        self,
        defaults: FakeDefaultsStore,
        discovery: FakeDiscovery,
        manager: FakeSyncManager,
    ) -> None:
        super().__init__()
        self.defaults = defaults
        self.discovery = discovery
        self.manager = manager

    @provide
    def defaults_store(self) -> DefaultsStore:
        return self.defaults

    @provide
    def discovery_service(self) -> Discovery:
        return self.discovery

    @provide
    def sync_manager(self) -> SyncManager:
        return self.manager


@dataclass
class Api:
    client: TestClient
    defaults: FakeDefaultsStore
    discovery: FakeDiscovery
    manager: FakeSyncManager


@pytest.fixture
def api() -> Iterator[Api]:
    defaults = FakeDefaultsStore()
    discovery = FakeDiscovery()
    manager = FakeSyncManager()
    container = make_async_container(FakeProvider(defaults, discovery, manager))
    app = FastAPI()
    app.include_router(router)
    setup_dishka(container, app)

    with TestClient(app) as client:
        yield Api(client, defaults, discovery, manager)

    asyncio.run(container.close())


def test_status_reports_manager_state(api: Api) -> None:
    api.manager.running = True
    api.manager.area = "Office"

    response = api.client.get("/status")

    assert response.status_code == 200
    assert response.json() == {"running": True, "area": "Office"}


def test_start_resolves_request_and_starts_manager(api: Api) -> None:
    api.defaults.resolved = ResolvedSettings(area="Office")

    response = api.client.post(
        "/start",
        json={"analysis": {"sensitivity": 1.7}},
    )

    assert response.status_code == 200
    assert response.json() == {"running": True, "area": "Office"}
    assert api.defaults.last_request == SyncSettings(analysis={"sensitivity": 1.7})
    assert api.manager.settings is api.defaults.resolved


def test_start_requires_an_area(api: Api) -> None:
    api.defaults.resolved = ResolvedSettings()

    response = api.client.post("/start", json={})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("area is required")
    assert api.manager.settings is None


@pytest.mark.parametrize(
    "error",
    [
        SyncAlreadyRunning("already running"),
        ValueError("invalid mode"),
        RuntimeError("bridge rejected stream"),
    ],
)
def test_start_maps_runtime_failures_to_conflict(api: Api, error: Exception) -> None:
    api.manager.start_error = error

    response = api.client.post("/start", json={})

    assert response.status_code == 409
    assert response.json() == {"detail": str(error)}


def test_stop_stops_active_sync(api: Api) -> None:
    api.manager.running = True
    api.manager.area = "Living Room"

    response = api.client.post("/stop")

    assert response.status_code == 200
    assert response.json() == {"running": False, "area": None}


def test_stop_reports_when_no_sync_is_running(api: Api) -> None:
    api.manager.stop_error = SyncNotRunning("no sync is running")

    response = api.client.post("/stop")

    assert response.status_code == 409
    assert response.json() == {"detail": "no sync is running"}


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/devices", "Speakers (loopback)"),
        ("/areas", "Living Room"),
    ],
)
def test_discovery_routes_return_available_choices(
    api: Api, path: str, expected: str
) -> None:
    response = api.client.get(path)

    assert response.status_code == 200
    assert response.json()[0]["name"] == expected


@pytest.mark.parametrize("path", ["/devices", "/areas"])
def test_discovery_routes_report_unavailable_backends(api: Api, path: str) -> None:
    api.discovery.error = DiscoveryUnavailable("backend unavailable")

    response = api.client.get(path)

    assert response.status_code == 503
    assert response.json() == {"detail": "backend unavailable"}


def test_defaults_can_be_read_and_replaced(api: Api) -> None:
    current = api.client.get("/defaults")
    updated = api.client.put(
        "/defaults",
        json={"area": "Office", "visual": {"rate": 30}},
    )

    assert current.status_code == 200
    assert current.json()["area"] == "Living Room"
    assert updated.status_code == 200
    assert updated.json()["area"] == "Office"
    assert updated.json()["visual"]["rate"] == 30
    assert api.defaults.current == SyncSettings(area="Office", visual={"rate": 30})
