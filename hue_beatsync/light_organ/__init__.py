"""A light organ: microphone in, Hue entertainment frames out.

    audio.AudioCapture      the microphone, on PortAudio's thread
    analysis.SpectralAnalyzer   blocks -> bands, beats, tempo
    visuals.Visual          features -> colors for one entertainment area

The two runners live one directory up: ``mic_capture.py`` shows the analysis in
the terminal without touching the bridge, ``light_organ_stream.py`` sends it to
the lights.
"""

from light_organ.analysis import BAND_NAMES, AudioFeatures, SpectralAnalyzer
from light_organ.audio import AudioCapture, AudioDevice, input_devices, resolve_device
from light_organ.smoothing import Envelope, PeakFollower
from light_organ.visuals import MODES, Pulse, Spectrum, Sweep, Visual, channel_positions

__all__ = [
    "BAND_NAMES",
    "MODES",
    "AudioCapture",
    "AudioDevice",
    "AudioFeatures",
    "Envelope",
    "PeakFollower",
    "Pulse",
    "SpectralAnalyzer",
    "Spectrum",
    "Sweep",
    "Visual",
    "channel_positions",
    "input_devices",
    "resolve_device",
]
