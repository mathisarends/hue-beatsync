import pytest

from lichtorgel import diagnostics
from lichtorgel.analysis import AudioFeatures
from lichtorgel.audio import AudioDevice

SILENT = AudioFeatures((0.0,) * 5, 0.0, 0.5, 4, 0.0, 0.0, None, 0.0, True)
ACTIVE = AudioFeatures(
    (0.2, 0.4, 0.6, 0.8, 1.0), 0.7, 0.6, 6, 0.8, 0.5, 120.0, 0.03, False
)


class Analyzer:
    def __init__(self, _samplerate):
        self.snapshots = iter((SILENT, ACTIVE))
        self.current = SILENT

    @property
    def features(self):
        self.current = next(self.snapshots, self.current)
        return self.current

    def feed(self, _block, _delta):
        pass


class Capture:
    failure = None
    dropouts = 1
    latency = 0.012

    def __init__(self, _device, _listener, **_settings):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass


async def test_audio_diagnostic_is_finite_and_summarizes_features(monkeypatch):
    device = AudioDevice(2, "Loopback", 48_000, 2, "WASAPI")
    monkeypatch.setattr(diagnostics, "resolve_device", lambda _wanted: device)
    monkeypatch.setattr(diagnostics, "SpectralAnalyzer", Analyzer)
    monkeypatch.setattr(diagnostics, "SoundDeviceCapture", Capture)

    result = await diagnostics.diagnose_audio(duration=0.002, interval=0.001)

    assert result.device is device
    assert result.audio_detected is True
    assert result.beats == 2
    assert result.bpm == 120.0
    assert result.dropouts == 1
    assert result.levels == ACTIVE.levels


@pytest.mark.parametrize("duration", [0.0, -1.0])
async def test_audio_diagnostic_rejects_non_positive_duration(duration):
    with pytest.raises(ValueError, match="duration"):
        await diagnostics.diagnose_audio(duration=duration)
