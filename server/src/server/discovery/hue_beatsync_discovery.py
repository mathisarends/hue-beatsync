import asyncio

import httpx
from hue_beatsync import AudioDevice, input_devices, resolve_device
from hue_beatsync.areas import BeatSyncArea, list_areas
from hueify.errors import HueifyError

from server.discovery.base import Discovery, DiscoveryUnavailable
from server.schemas import AreaInfo, AudioDeviceInfo


class HueBeatSyncDiscovery(Discovery):
    """Discovery backed by the local audio backend and the Hue bridge."""

    async def devices(self) -> list[AudioDeviceInfo]:
        try:
            devices, default = await asyncio.to_thread(self._query_devices)
        except RuntimeError as error:
            raise DiscoveryUnavailable(str(error)) from error
        return [
            _device(device, is_default=device.index == default) for device in devices
        ]

    async def areas(self) -> list[AreaInfo]:
        try:
            areas = await list_areas()
        except (HueifyError, httpx.HTTPError, RuntimeError, ValueError) as error:
            raise DiscoveryUnavailable(str(error)) from error
        return [_area(area) for area in areas]

    def _query_devices(self) -> tuple[list[AudioDevice], int | None]:
        """Both queries hit the blocking audio backend, so they share a thread."""
        devices = input_devices()
        try:
            default = resolve_device().index
        except RuntimeError:
            default = None
        return devices, default


def _device(device: AudioDevice, *, is_default: bool) -> AudioDeviceInfo:
    return AudioDeviceInfo(
        index=device.index,
        name=device.name,
        samplerate=device.samplerate,
        channels=device.channels,
        host_api=device.host_api,
        is_default=is_default,
        # Mirrors the guard in SoundDeviceCapture: exclusive mode is WASAPI-only.
        supports_exclusive="WASAPI" in device.host_api,
    )


def _area(area: BeatSyncArea) -> AreaInfo:
    return AreaInfo(
        id=area.id,
        name=area.name,
        active=area.active,
        channels=area.channels,
    )
