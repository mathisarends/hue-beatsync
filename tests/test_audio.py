from types import SimpleNamespace

import numpy as np
import pytest

from hue_beatsync.audio import AudioCapture, sounddevice
from hue_beatsync.audio.sounddevice import AudioDevice, SoundDeviceCapture


@pytest.fixture
def devices():
    return [
        AudioDevice(2, "Built-in Microphone", 48_000, 2, "WASAPI"),
        AudioDevice(7, "USB Microphone", 44_100, 1, "MME"),
    ]


def test_resolve_device_by_index_name_and_default(monkeypatch, devices):
    backend = SimpleNamespace(default=SimpleNamespace(device=(7, None)))
    monkeypatch.setattr(sounddevice, "input_devices", lambda: devices)
    monkeypatch.setattr(sounddevice, "_load_sounddevice", lambda: backend)

    assert sounddevice.resolve_device().index == 7
    assert sounddevice.resolve_device("2").index == 2
    assert sounddevice.resolve_device("usb").index == 7


def test_resolve_device_reports_available_inputs(monkeypatch, devices):
    monkeypatch.setattr(sounddevice, "input_devices", lambda: devices)

    with pytest.raises(RuntimeError, match="Built-in Microphone"):
        sounddevice.resolve_device("missing")


def test_capture_callback_downmixes_and_records_failure(devices):
    received = []
    capture = SoundDeviceCapture(
        devices[0], lambda block, delta: received.append((block, delta))
    )
    stereo = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    capture._on_block(stereo, 2, None, SimpleNamespace(input_overflow=True))

    assert received[0][0] == pytest.approx([0.5, 0.5])
    assert received[0][1] == pytest.approx(2 / 48_000)
    assert capture.dropouts == 1

    failing = SoundDeviceCapture(
        devices[0], lambda *_: (_ for _ in ()).throw(ValueError("bad"))
    )
    failing._on_block(stereo, 2, None, SimpleNamespace(input_overflow=False))
    assert isinstance(failing.failure, ValueError)


def test_capture_rejects_non_positive_block_size(devices):
    with pytest.raises(ValueError, match="block_size"):
        SoundDeviceCapture(devices[0], lambda *_: None, block_size=0)


def test_sounddevice_capture_implements_capture_contract(devices):
    capture: AudioCapture = SoundDeviceCapture(devices[0], lambda *_: None)

    assert capture.samplerate == 48_000
