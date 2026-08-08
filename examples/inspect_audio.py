import argparse
import contextlib
import time

from examples.console import bar
from hue_beatsync.analysis import SpectralAnalyzer, band_edges
from hue_beatsync.audio import AudioCapture
from hue_beatsync.audio.sounddevice import (
    SoundDeviceCapture,
    input_devices,
    resolve_device,
)

_REFRESH_RATE = 30
_DEFAULT_SENSITIVITY = 1.2
_DEFAULT_MAX_FREQUENCY = 14_000.0

_BAND_LABELS = ("BASS", "LOW", "MID", "HIGH", "TRE")
_BAND_COLORS = (31, 33, 32, 36, 35)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect microphone analysis without connecting to a Hue bridge."
    )
    parser.add_argument("--device", help="input device index or part of its name")
    parser.add_argument("--seconds", type=float, help="stop after this long")
    parser.add_argument(
        "--sensitivity",
        type=float,
        default=_DEFAULT_SENSITIVITY,
        help="beat threshold in standard deviations, lower finds more beats",
    )
    parser.add_argument(
        "--max-freq",
        type=float,
        default=_DEFAULT_MAX_FREQUENCY,
        help="squeeze the bands below this, for a mic that cannot hear higher",
    )
    parser.add_argument(
        "--list", action="store_true", help="show the input devices and exit"
    )
    args = parser.parse_args()

    if args.list:
        for device in input_devices():
            print(device)
        return

    device = resolve_device(args.device)
    analyzer = SpectralAnalyzer(
        device.samplerate,
        sensitivity=args.sensitivity,
        edges=band_edges(args.max_freq),
    )

    print(f"Listening on {device}")
    edges = "  ".join(
        f"{label} {low:.0f}-{high:.0f}"
        for label, (low, high) in zip(_BAND_LABELS, analyzer.bands, strict=True)
    )
    print(f"Bands: {edges} Hz")
    print("Play something loud enough to hear across the room. Ctrl+C stops.\n")

    with (
        SoundDeviceCapture(device, analyzer.feed) as capture,
        contextlib.suppress(KeyboardInterrupt),
    ):
        _watch(analyzer, capture, args.seconds)

    features = analyzer.features
    print("\n")
    print(f"Beats detected : {features.beats}")
    print(f"Tempo estimate : {_tempo(features.bpm)}")
    print(f"Input latency  : {capture.latency * 1000:.0f} ms")
    print(f"Dropouts       : {capture.dropouts}")
    if capture.failure is not None:
        print(f"Analysis failed: {capture.failure!r}")


def _watch(
    analyzer: SpectralAnalyzer, capture: AudioCapture, seconds: float | None
) -> None:
    deadline = None if seconds is None else time.monotonic() + seconds
    seen_beats = analyzer.features.beats
    beat_shown_at = 0.0

    while deadline is None or time.monotonic() < deadline:
        now = time.monotonic()
        features = analyzer.features

        if features.beats > seen_beats:
            seen_beats = features.beats
            beat_shown_at = now

        bars = " ".join(
            f"\x1b[{color}m{label}\x1b[0m {bar(level)}"
            for label, color, level in zip(
                _BAND_LABELS, _BAND_COLORS, features.levels, strict=True
            )
        )
        beat = "\x1b[97m*BEAT\x1b[0m" if now - beat_shown_at < 0.12 else "     "
        state = "quiet" if features.silent else f"{_tempo(features.bpm):>9}"

        print(f"\r{bars}  {beat}  {state}  ", end="", flush=True)
        time.sleep(1 / _REFRESH_RATE)

        if capture.failure is not None:
            return


def _tempo(bpm: float | None) -> str:
    return "-- BPM" if bpm is None else f"{bpm:.0f} BPM"


if __name__ == "__main__":
    main()
