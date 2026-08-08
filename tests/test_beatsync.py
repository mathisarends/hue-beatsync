from types import SimpleNamespace

import pytest

from hue_beatsync import beatsync
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


class Hue:
    def __init__(self, entertainment):
        self.entertainment = entertainment
        self.open = False

    async def __aenter__(self):
        self.open = True
        return self

    async def __aexit__(self, *_args):
        self.open = False


@pytest.fixture
def device():
    return AudioDevice(2, "Microphone", 48_000, 2, "WASAPI")


@pytest.fixture
def area():
    return SimpleNamespace(name="Music", is_streaming=False)


async def test_context_connects_capture_analysis_visual_and_stream(
    monkeypatch, device, area
):
    entertainment = Entertainment(area)
    hue = Hue(entertainment)
    monkeypatch.setattr(beatsync, "Hueify", lambda: hue)
    sync = BeatSync("Music", device=device, mode="spectrum", rate=40)
    capture = Capture()
    sync.capture = capture

    async with sync:
        assert hue.open is True
        assert capture.started is True
        assert entertainment.stream_instance.open is True
        await sync.run()

    assert sync.stream is entertainment.stream_instance
    assert sync.visual is entertainment.stream_instance.visual
    assert entertainment.opened is area
    assert entertainment.rate == 40
    assert hue.open is False
    assert capture.started is False
    assert entertainment.stream_instance.open is False


async def test_context_rejects_an_area_owned_by_another_application(
    monkeypatch, device
):
    area = SimpleNamespace(name="Music", is_streaming=True)
    entertainment = Entertainment(area)
    hue = Hue(entertainment)
    monkeypatch.setattr(beatsync, "Hueify", lambda: hue)
    sync = BeatSync("Music", device=device)

    with pytest.raises(RuntimeError, match="already streaming"):
        async with sync:
            pass

    assert entertainment.opened is None
    assert hue.open is False


async def test_run_propagates_capture_callback_failure(monkeypatch, device, area):
    entertainment = Entertainment(area)
    monkeypatch.setattr(beatsync, "Hueify", lambda: Hue(entertainment))
    sync = BeatSync("Music", device=device)
    failure = ValueError("analysis failed")
    sync.capture = Capture(failure)

    with pytest.raises(ValueError, match="analysis failed"):
        async with sync:
            await sync.run()

    assert entertainment.stream_instance.open is False


async def test_run_rejects_negative_duration(device):
    sync = BeatSync("Music", device=device)

    with pytest.raises(ValueError, match="seconds"):
        await sync.run(-1)


async def test_run_requires_open_context(device):
    sync = BeatSync("Music", device=device)

    with pytest.raises(RuntimeError, match="async with"):
        await sync.run()


def test_area_name_must_not_be_empty(device):
    with pytest.raises(ValueError, match="area_name"):
        BeatSync("  ", device=device)
