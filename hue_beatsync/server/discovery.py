import asyncio
from typing import Protocol

import httpx
from hueify.errors import HueifyError

from hue_beatsync import AudioDevice, input_devices, resolve_device
from hue_beatsync.areas import EntertainmentArea, list_areas
from hue_beatsync.server.schemas import AreaInfo, AudioDeviceInfo


class DiscoveryUnavailable(RuntimeError):
    """The audio backend or Hue bridge could not be reached."""


class Discovery(Protocol):
    async def devices(self) -> list[AudioDeviceInfo]: ...

    async def areas(self) -> list[AreaInfo]: ...


class HueDiscovery(Discovery):
    """Discovery backed by the local audio backend and the Hue bridge."""

    async def devices(self) -> list[AudioDeviceInfo]:
        try:
            devices, default = await asyncio.to_thread(self._query_devices)
        except RuntimeError as error:
            raise DiscoveryUnavailable(str(error)) from error
        # PortAudio loads fine without any sound hardware behind it - the usual
        # case is a container, where it reports ALSA with zero devices. An empty
        # list would look like a valid answer, so report it as unavailable.
        if not devices:
            raise DiscoveryUnavailable(
                "No audio input device found. The audio backend loaded but "
                "reports no inputs, which is what a container without access to "
                "the host sound hardware looks like - see the server README."
            )
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


def _area(area: EntertainmentArea) -> AreaInfo:
    return AreaInfo(
        id=area.id,
        name=area.name,
        active=area.active,
        channels=area.channels,
    )
