import argparse
import asyncio
import contextlib

from hue_beatsync import BeatSync, input_devices, visual_names

_DEFAULT_AREA = "Musikbereich"
_DEFAULT_SENSITIVITY = 1.2
_DEFAULT_GAMMA = 1.0
_DEFAULT_FLOOR = 0.12
_DEFAULT_MAX_FREQUENCY = 14_000.0


async def main() -> None:
    args = _parse_args()

    if args.list:
        for device in input_devices():
            print(device)
        return

    sync = BeatSync(
        args.area,
        device=args.device,
        mode=args.mode,
        rate=args.rate,
        sensitivity=args.sensitivity,
        gamma=args.gamma,
        floor=args.floor,
        max_frequency=args.max_freq,
        exclusive=args.exclusive,
        gain=args.gain,
    )
    async with sync:
        await sync.run(args.seconds)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream microphone-driven visuals to a Hue entertainment area."
    )
    parser.add_argument("--area", default=_DEFAULT_AREA, help="entertainment area name")
    parser.add_argument(
        "--mode",
        default="pulse",
        choices=visual_names(),
        help="which light show to run",
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
        "--gamma",
        type=float,
        default=_DEFAULT_GAMMA,
        help="brightness contrast, above 1 darkens the quiet parts",
    )
    parser.add_argument(
        "--floor",
        type=float,
        default=_DEFAULT_FLOOR,
        help="brightness the lamps never fall below while audio is playing",
    )
    parser.add_argument(
        "--max-freq",
        type=float,
        default=_DEFAULT_MAX_FREQUENCY,
        help="squeeze the bands below this, for a mic that cannot hear higher",
    )
    parser.add_argument(
        "--exclusive",
        action="store_true",
        help="WASAPI direct hardware access, skipping Windows' effects chain",
    )
    parser.add_argument(
        "--gain",
        type=float,
        default=1.0,
        help="multiply the signal, exclusive mode is often much quieter",
    )
    parser.add_argument("--rate", type=int, default=50, help="frames per second")
    parser.add_argument(
        "--list", action="store_true", help="show the input devices and exit"
    )
    return parser.parse_args()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
