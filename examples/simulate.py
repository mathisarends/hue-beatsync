import argparse
import wave
from pathlib import Path

import numpy as np
from hueify.entertainment import Frame, Tick

from examples.console import sparkline
from hue_beatsync.analysis import SpectralAnalyzer, band_edges
from hue_beatsync.visuals import create_visual, visual_names

_RATE = 48_000
_BLOCK = 512
_FPS = 50
_DEFAULT_SENSITIVITY = 1.2
_DEFAULT_GAMMA = 1.0
_DEFAULT_MAX_FREQUENCY = 14_000.0

_LAYOUTS = {
    "asymmetric": {0: 0.3, 1: 0.84, 2: 1.0, 3: 1.0},
    "wide": {0: -0.82, 1: -0.2, 2: 0.75, 3: 0.8, 4: 1.0},
    "even": {index: -1.0 + index * 0.5 for index in range(5)},
}


def make_track(bpm: float, seconds: float) -> np.ndarray:
    """A kick on every beat, a hat on every offbeat, and a sustained pad."""
    total = int(_RATE * seconds)
    time = np.arange(total) / _RATE
    audio = np.zeros(total, dtype=np.float32)
    beat = 60.0 / bpm

    for index in range(int(seconds / beat)):
        start = int(index * beat * _RATE)
        span = np.arange(min(int(0.18 * _RATE), total - start)) / _RATE
        audio[start : start + len(span)] += (
            0.9 * np.sin(2 * np.pi * 55 * span) * np.exp(-span * 22)
        ).astype(np.float32)

        offbeat = int((index + 0.5) * beat * _RATE)
        span = np.arange(min(int(0.05 * _RATE), max(total - offbeat, 0))) / _RATE
        if len(span):
            noise = np.random.default_rng(index).normal(0, 1, len(span))
            audio[offbeat : offbeat + len(span)] += (
                0.25 * noise * np.exp(-span * 90)
            ).astype(np.float32)

    audio += (0.12 * np.sin(2 * np.pi * 440 * time)).astype(np.float32)
    audio += (0.08 * np.sin(2 * np.pi * 1800 * time)).astype(np.float32)
    return audio


def _rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(audio))))


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """A recording as mono float32, alongside its sample rate."""
    with wave.open(str(path)) as handle:
        if handle.getsampwidth() != 2:
            raise ValueError(f"Only 16 bit WAV is supported, {path} is not")
        frames = np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2")
        channels = handle.getnchannels()
        rate = handle.getframerate()

    audio = frames.astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, rate


def run(
    audio: np.ndarray,
    rate: int,
    mode: str,
    layout: dict[int, float],
    args: argparse.Namespace,
) -> tuple[list[float], int, float | None]:
    """Interleave analysis and rendering the way the real runner does."""
    analyzer = SpectralAnalyzer(
        rate, sensitivity=args.sensitivity, edges=band_edges(args.max_freq)
    )
    frame = Frame(layout)
    visual = create_visual(mode, layout, analyzer, gamma=args.gamma)

    interval = 1 / _FPS
    elapsed = last_render = 0.0
    next_frame = interval
    index = 0
    brightness = []

    for start in range(0, len(audio) - _BLOCK, _BLOCK):
        analyzer.feed(audio[start : start + _BLOCK], _BLOCK / rate)
        elapsed += _BLOCK / rate

        while next_frame <= elapsed:
            visual.render(frame, Tick(index, next_frame, next_frame - last_render))
            last_render, index = next_frame, index + 1
            next_frame += interval
            if args.window[0] <= last_render <= args.window[1]:
                colors = frame.colors().values()
                brightness.append(max(sum(color) / 3 for color in colors))

    return brightness, analyzer.features.beats, analyzer.features.bpm


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the analyzer and visuals against synthetic or WAV audio."
    )
    parser.add_argument("--mode", choices=visual_names(), help="only this mode")
    parser.add_argument("--layout", choices=tuple(_LAYOUTS), help="only this layout")
    parser.add_argument("--bpm", type=float, default=120.0)
    parser.add_argument("--seconds", type=float, default=12.0)
    parser.add_argument("--sensitivity", type=float, default=_DEFAULT_SENSITIVITY)
    parser.add_argument("--gamma", type=float, default=_DEFAULT_GAMMA)
    parser.add_argument("--max-freq", type=float, default=_DEFAULT_MAX_FREQUENCY)
    parser.add_argument("--wav", type=Path, help="run a recording instead")
    parser.add_argument(
        "--window",
        type=float,
        nargs=2,
        default=(4.0, 5.0),
        metavar=("FROM", "TO"),
        help="the seconds of the track to draw",
    )
    args = parser.parse_args()

    if args.wav:
        audio, rate = read_wav(args.wav)
        print(f"{args.wav} - {len(audio) / rate:.1f} s at {rate} Hz")
        print(f"  peak {np.max(np.abs(audio)):.4f}, rms {_rms(audio):.4f}")
    else:
        audio, rate = make_track(args.bpm, args.seconds), _RATE
        onsets = 2 * int(args.seconds / (60 / args.bpm))
        print(f"{args.bpm:.0f} BPM, {args.seconds:.0f} s, {onsets} onsets in the track")

    edges = band_edges(args.max_freq)
    print(f"sensitivity {args.sensitivity}, gamma {args.gamma}")
    print(f"bands {'  '.join(f'{edge:.0f}' for edge in edges)} Hz\n")

    modes = (args.mode,) if args.mode else visual_names()
    layouts = (args.layout,) if args.layout else tuple(_LAYOUTS)

    for name in layouts:
        print(f"{name} layout: {sorted(_LAYOUTS[name].values())}")
        for mode in modes:
            brightness, beats, bpm = run(audio, rate, mode, _LAYOUTS[name], args)
            low, high = min(brightness), max(brightness)
            mean = sum(brightness) / len(brightness)
            tempo = f"{bpm:>5.0f} BPM" if bpm else "   -- BPM"
            print(
                f"  {mode:<9} beats {beats:>3}  tempo {tempo}"
                f"  min {low:.2f}  max {high:.2f}  mean {mean:.2f}"
            )
            print(f"    {sparkline(brightness)}")
        print()


if __name__ == "__main__":
    main()
