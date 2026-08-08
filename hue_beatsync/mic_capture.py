"""Watch the microphone analysis in the terminal, without touching the bridge.

Use this first: it answers whether the room is loud enough, whether the bands
react the way you would expect and whether the beat detector locks onto the
tempo. Only when this looks right is it worth streaming to lights.

    python experiments/mic_capture.py --list
    python experiments/mic_capture.py
    python experiments/mic_capture.py --device "Mikrofonarray" --seconds 30
"""

from __future__ import annotations

import argparse
import contextlib
import time

from light_organ.analysis import (
    DEFAULT_SENSITIVITY,
    HIGHEST_FREQUENCY,
    SpectralAnalyzer,
    band_edges,
)
from light_organ.audio import AudioCapture, input_devices, resolve_device
from light_organ.console import bar

REFRESH_RATE = 30

BAND_LABELS = ("BASS", "LOW", "MID", "HIGH", "TRE")
BAND_COLORS = (31, 33, 32, 36, 35)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--device", help="input device index or part of its name")
    parser.add_argument("--seconds", type=float, help="stop after this long")
    parser.add_argument(
        "--sensitivity",
        type=float,
        default=DEFAULT_SENSITIVITY,
        help="beat threshold in standard deviations, lower finds more beats",
    )
    parser.add_argument(
        "--max-freq",
        type=float,
        default=HIGHEST_FREQUENCY,
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
        for label, (low, high) in zip(BAND_LABELS, analyzer.bands, strict=True)
    )
    print(f"Bands: {edges} Hz")
    print("Play something loud enough to hear across the room. Ctrl+C stops.\n")

    with (
        AudioCapture(device, analyzer.feed) as capture,
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
                BAND_LABELS, BAND_COLORS, features.levels, strict=True
            )
        )
        beat = "\x1b[97m*BEAT\x1b[0m" if now - beat_shown_at < 0.12 else "     "
        state = "quiet" if features.silent else f"{_tempo(features.bpm):>9}"

        print(f"\r{bars}  {beat}  {state}  ", end="", flush=True)
        time.sleep(1 / REFRESH_RATE)

        if capture.failure is not None:
            return


def _tempo(bpm: float | None) -> str:
    return "-- BPM" if bpm is None else f"{bpm:.0f} BPM"


if __name__ == "__main__":
    main()
