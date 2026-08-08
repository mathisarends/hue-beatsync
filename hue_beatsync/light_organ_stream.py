"""Drive a Hue entertainment area from whatever the microphone hears.

    pip install "hueify[entertainment]" sounddevice numpy
    hueify setup                      # also prints HUE_CLIENT_KEY

    python experiments/light_organ_stream.py --area "Musikbereich"
    python experiments/light_organ_stream.py --mode sweep --sensitivity 1.2

Check the analysis with ``mic_capture.py`` first if the lights look wrong - it
is almost always the microphone, not the mapping.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib

from light_organ.analysis import (
    DEFAULT_SENSITIVITY,
    HIGHEST_FREQUENCY,
    SpectralAnalyzer,
    band_edges,
)
from light_organ.audio import AudioCapture, input_devices, resolve_device
from light_organ.console import sparkline
from light_organ.visuals import DEFAULT_GAMMA, MODES, Visual, channel_positions

from hueify import Hueify
from hueify.entertainment import EntertainmentStream

DEFAULT_AREA = "Musikbereich"
REPORT_INTERVAL = 1.0


async def main() -> None:
    args = _parse_args()

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

    async with Hueify() as hue:
        area = await hue.entertainment.find_by_name(args.area)
        if area.is_streaming:
            print(f"{args.area} is already being streamed to by another application.")
            return

        print(f"Listening on {device}")

        with AudioCapture(device, analyzer.feed) as capture:
            async with hue.entertainment.stream(area, rate=args.rate) as stream:
                positions = channel_positions(stream.channels)
                visual = MODES[args.mode](positions, analyzer, gamma=args.gamma)
                print(
                    f"Streaming {args.mode} to {args.area}, "
                    f"{len(stream.channels)} channels at {stream.rate} fps, "
                    f"{capture.latency * 1000:.0f} ms input latency.\n"
                )
                await _run(stream, visual, analyzer, capture, args.seconds)

        print(
            f"\n\nSent {stream.stats.frames_sent} frames, "
            f"{stream.stats.late_frames} late, {capture.dropouts} audio dropouts."
        )
        if capture.failure is not None:
            print(f"The analysis raised {capture.failure!r}")


async def _run(
    stream: EntertainmentStream,
    visual: Visual,
    analyzer: SpectralAnalyzer,
    capture: AudioCapture,
    seconds: float | None,
) -> None:
    reporter = asyncio.create_task(_report(stream, analyzer, capture))
    try:
        async with asyncio.timeout(seconds):
            await stream.run(visual)
    except TimeoutError:
        pass
    finally:
        reporter.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reporter


async def _report(
    stream: EntertainmentStream, analyzer: SpectralAnalyzer, capture: AudioCapture
) -> None:
    """A live line to judge quality by: is it hearing beats, is it keeping up."""
    while True:
        await asyncio.sleep(REPORT_INTERVAL)
        if capture.failure is not None:
            return

        features = analyzer.features
        bars = sparkline(features.levels)
        bpm = "-- BPM" if features.bpm is None else f"{features.bpm:.0f} BPM"
        state = "quiet" if features.silent else bpm
        print(
            f"\r{bars}  {features.beats:>5} beats  {state:>8}  "
            f"{stream.stats.late_frames} late frames  ",
            end="",
            flush=True,
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--area", default=DEFAULT_AREA, help="entertainment area name")
    parser.add_argument(
        "--mode", default="pulse", choices=tuple(MODES), help="which light show to run"
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
        "--gamma",
        type=float,
        default=DEFAULT_GAMMA,
        help="brightness contrast, above 1 darkens the quiet parts",
    )
    parser.add_argument(
        "--max-freq",
        type=float,
        default=HIGHEST_FREQUENCY,
        help="squeeze the bands below this, for a mic that cannot hear higher",
    )
    parser.add_argument("--rate", type=int, default=50, help="frames per second")
    parser.add_argument(
        "--list", action="store_true", help="show the input devices and exit"
    )
    return parser.parse_args()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
