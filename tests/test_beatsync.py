from types import SimpleNamespace

import pytest

from hue_beatsync.audio.sounddevice import AudioDevice
from hue_beatsync.beatsync import BeatSync


class Capture:
    def __init__(self, failure=None):
        self.failure = failure
        self.started = False

    def __enter__(self):
        self.started = True
        return self

    def __exit__(self, *_args):
        self.started = False


class Stream:
    def __init__(self):
        self.channels = [SimpleNamespace(channel_id=1, position=SimpleNamespace(x=0.0))]
        self.visual = None
        self.open = False

    async def __aenter__(self):
        self.open = True
        return self

    async def __aexit__(self, *_args):
        self.open = False

    async def run(self, visual):
        self.visual = visual


class Entertainment:
    def __init__(self, area):
        self.area = area
        self.opened = None
        self.rate = None
        self.stream_instance = Stream()

    async def find_by_name(self, name):
        assert name == self.area.name
        return self.area

    def stream(self, area, rate):
        self.opened = area
        self.rate = rate
        return self.stream_instance


@pytest.fixture
def device():
    return AudioDevice(2, "Microphone", 48_000, 2, "WASAPI")


@pytest.fixture
def area():
    return SimpleNamespace(name="Music", is_streaming=False)


async def test_run_connects_capture_analysis_visual_and_stream(device, area):
    entertainment = Entertainment(area)
    hue = SimpleNamespace(entertainment=entertainment)
    sync = BeatSync("Music", hue=hue, device=device, mode="spectrum", rate=40)
    capture = Capture()
    sync.capture = capture

    await sync.run()

    assert sync.stream is entertainment.stream_instance
    assert sync.visual is entertainment.stream_instance.visual
    assert entertainment.opened is area
    assert entertainment.rate == 40
    assert capture.started is False


async def test_run_rejects_an_area_owned_by_another_application(device):
    area = SimpleNamespace(name="Music", is_streaming=True)
    entertainment = Entertainment(area)
    sync = BeatSync(
        "Music", hue=SimpleNamespace(entertainment=entertainment), device=device
    )

    with pytest.raises(RuntimeError, match="already streaming"):
        await sync.run()

    assert entertainment.opened is None


async def test_run_propagates_capture_callback_failure(device, area):
    entertainment = Entertainment(area)
    sync = BeatSync(
        area, hue=SimpleNamespace(entertainment=entertainment), device=device
    )
    failure = ValueError("analysis failed")
    sync.capture = Capture(failure)

    with pytest.raises(ValueError, match="analysis failed"):
        await sync.run()

    assert entertainment.stream_instance.open is False


async def test_run_rejects_negative_duration(device):
    sync = BeatSync("Music", hue=SimpleNamespace(), device=device)

    with pytest.raises(ValueError, match="seconds"):
        await sync.run(-1)
