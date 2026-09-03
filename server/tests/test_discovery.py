from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

import server.discovery as discovery_module
from server.discovery import DiscoveryUnavailable, HueDiscovery


@pytest.fixture(autouse=True)
def run_blocking_calls_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def to_thread(function: Callable[[], Any]) -> Any:
        return function()

    monkeypatch.setattr(discovery_module.asyncio, "to_thread", to_thread)


def test_query_devices_returns_inputs_and_default_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    devices = [object()]
    monkeypatch.setattr(discovery_module, "input_devices", lambda: devices)
    monkeypatch.setattr(
        discovery_module,
        "resolve_device",
        lambda: SimpleNamespace(index=3),
    )

    result = HueDiscovery()._query_devices()

    assert result == (devices, 3)


def test_query_devices_tolerates_a_missing_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    devices = [object()]

    def fail_to_resolve() -> None:
        raise RuntimeError("no default device")

    monkeypatch.setattr(discovery_module, "input_devices", lambda: devices)
    monkeypatch.setattr(discovery_module, "resolve_device", fail_to_resolve)

    result = HueDiscovery()._query_devices()

    assert result == (devices, None)


@pytest.mark.asyncio
async def test_devices_map_backend_data_and_mark_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery = HueDiscovery()
    devices = [
        SimpleNamespace(
            index=3,
            name="Speakers",
            samplerate=48_000,
            channels=2,
            host_api="Windows WASAPI",
        ),
        SimpleNamespace(
            index=4,
            name="Microphone",
            samplerate=44_100,
            channels=1,
            host_api="MME",
        ),
    ]
    monkeypatch.setattr(discovery, "_query_devices", lambda: (devices, 3))

    result = await discovery.devices()

    assert [device.index for device in result] == [3, 4]
    assert result[0].is_default is True
    assert result[0].supports_exclusive is True
    assert result[1].is_default is False
    assert result[1].supports_exclusive is False


@pytest.mark.asyncio
async def test_devices_report_an_empty_backend_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery = HueDiscovery()
    monkeypatch.setattr(discovery, "_query_devices", lambda: ([], None))

    with pytest.raises(DiscoveryUnavailable, match="No audio input device found"):
        await discovery.devices()


@pytest.mark.asyncio
async def test_device_backend_failures_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery = HueDiscovery()

    def fail() -> None:
        raise RuntimeError("PortAudio failed")

    monkeypatch.setattr(discovery, "_query_devices", fail)

    with pytest.raises(DiscoveryUnavailable, match="PortAudio failed"):
        await discovery.devices()


@pytest.mark.asyncio
async def test_areas_map_bridge_data(monkeypatch: pytest.MonkeyPatch) -> None:
    async def list_fake_areas() -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                id="area-1",
                name="Living Room",
                active=True,
                channels=3,
            )
        ]

    monkeypatch.setattr(discovery_module, "list_areas", list_fake_areas)

    result = await HueDiscovery().areas()

    assert result[0].model_dump() == {
        "id": "area-1",
        "name": "Living Room",
        "active": True,
        "channels": 3,
    }


@pytest.mark.asyncio
async def test_area_backend_failures_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail() -> None:
        raise RuntimeError("bridge offline")

    monkeypatch.setattr(discovery_module, "list_areas", fail)

    with pytest.raises(DiscoveryUnavailable, match="bridge offline"):
        await HueDiscovery().areas()
