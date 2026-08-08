"""Record the same moment through several microphones and compare what arrives.

Not every input hears music. A speakerphone runs echo cancellation and noise
suppression, which is built to remove exactly what comes out of the speakers,
and it is band limited to speech on top of that - so the bass simply is not in
the signal, and a light organ has nothing to work with.

Play something with a solid beat, then:

    python experiments/compare_inputs.py
    python experiments/compare_inputs.py --seconds 5 --device 17 --device 32

The bars are the raw spectrum, not the normalized levels the light show uses:
here the point is how the bands compare to each other on one device, and how
loud that device is against the others.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
import sounddevice as sd
from light_organ.analysis import BAND_EDGES, BAND_NAMES
from light_organ.audio import AudioDevice, input_devices, resolve_device
from light_organ.console import bar

WINDOW = 2048
BAND_LABELS = ("BASS", "LOW", "MID", "HIGH", "TRE")

# Below this a device is not hearing the room, it is showing its own noise
# floor. Its band shape is meaningless and must not be drawn: dividing noise by
# its own maximum produces five full bars, which reads as a perfect microphone.
DEAF = 1e-3


@dataclass(frozen=True, slots=True)
class Reading:
    device: AudioDevice
    loudness: float
    bands: tuple[float, ...]
    error: str | None = None

    @property
    def deaf(self) -> bool:
        """Too quiet for the band shape to mean anything."""
        return self.error is not None or self.loudness < DEAF

    @property
    def top_band(self) -> int:
        """The highest band that carries real energy, as an index."""
        return max(
            (index for index, level in enumerate(self.bands) if level > 0.1),
            default=0,
        )


def listen(device: AudioDevice, seconds: float) -> Reading:
    try:
        recording = sd.rec(
            int(seconds * device.samplerate),
            samplerate=device.samplerate,
            channels=min(device.channels, 2),
            device=device.index,
            dtype="float32",
        )
        sd.wait()
    except Exception as error:
        return Reading(device, 0.0, (0.0,) * len(BAND_NAMES), str(error).strip())

    mono = recording.mean(axis=1)
    return Reading(
        device, float(np.sqrt(np.mean(np.square(mono)))), _bands(mono, device)
    )


def _bands(mono: np.ndarray, device: AudioDevice) -> tuple[float, ...]:
    """Average spectrum per band, scaled so the loudest band of this device is 1.

    Scaling per device is the whole point: it shows the *shape* of what each
    microphone hears. A speech-tuned input has its energy in the mids with
    nothing below, whichever way its gain happens to be set.
    """
    window = np.hanning(WINDOW)
    frequencies = np.fft.rfftfreq(WINDOW, 1 / device.samplerate)
    spectra = [
        np.abs(np.fft.rfft(mono[start : start + WINDOW] * window))
        for start in range(0, len(mono) - WINDOW, WINDOW // 2)
    ]
    if not spectra:
        return (0.0,) * len(BAND_NAMES)

    average = np.mean(spectra, axis=0)
    energies = []
    for low, high in pairwise(BAND_EDGES):
        bins = np.flatnonzero((frequencies >= low) & (frequencies < high))
        energies.append(float(average[bins].mean()) if bins.size else 0.0)

    loudest = max(energies)
    return (
        tuple(energy / loudest for energy in energies) if loudest else tuple(energies)
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--device",
        action="append",
        help="test only this device, repeatable; defaults to one per host API",
    )
    parser.add_argument("--seconds", type=float, default=4.0)
    args = parser.parse_args()

    devices = (
        [resolve_device(wanted) for wanted in args.device]
        if args.device
        else input_devices()
    )

    print(f"Recording {args.seconds:.0f} s per device. Play music, loud.\n")
    print(f"{'device':<44} {'level':>7}  " + "  ".join(f"{n:<11}" for n in BAND_LABELS))

    readings = []
    for device in devices:
        print(f"{_name(device):<44} ...", end="\r", flush=True)
        reading = listen(device, args.seconds)
        readings.append(reading)

        if reading.error is not None:
            print(f"{_name(device):<44} {'-':>7}  cannot open: {reading.error[:40]}")
        elif reading.deaf:
            print(f"{_name(device):<44} {reading.loudness:>7.4f}  silent")
        else:
            bars = "  ".join(bar(level, 8) for level in reading.bands)
            print(f"{_name(device):<44} {reading.loudness:>7.4f}  {bars}")

    _advise(readings)


def _advise(readings: list[Reading]) -> None:
    heard = [reading for reading in readings if not reading.deaf]
    print()
    if not heard:
        print("Every input was silent. Either nothing was playing, or the inputs")
        print("are muted or turned down in the Windows sound settings.")
        return

    best = max(heard, key=lambda reading: reading.loudness)
    # By name, not by index: Windows renumbers its devices whenever one appears
    # or disappears, so today's 18 is tomorrow's something else entirely.
    print(f'Loudest, so the best bet:  --device "{_selector(best.device)}"')
    print(f"  {_name(best.device)}")

    ceiling = BAND_EDGES[best.top_band + 1]
    if best.top_band < len(BAND_NAMES) - 1:
        print(f"\n  It carries nothing above roughly {ceiling:.0f} Hz, so the top")
        print(
            f"  {len(BAND_NAMES) - 1 - best.top_band} band(s) would stay dark. Squeeze"
        )
        print(f"  the bands into what it can hear:  --max-freq {ceiling:.0f}")

    silent = [reading for reading in readings if reading.deaf and reading.error is None]
    if silent:
        print(
            f"\n{len(silent)} input(s) picked up nothing at all. If your built-in mic"
        )
        print("is among them, check its level in Windows sound settings - a dead")
        print("signal there is a muted or zeroed input, not a bad microphone.")


def _name(device: AudioDevice) -> str:
    return f"[{device.index}] {device.name[:30]} ({device.host_api})"[:44]


def _selector(device: AudioDevice) -> str:
    """The shortest piece of the name that still picks this device out."""
    words = device.name.split()
    for length in range(1, len(words) + 1):
        candidate = " ".join(words[:length])
        matches = [
            other
            for other in input_devices()
            if candidate.casefold() in other.name.casefold()
        ]
        if len({other.name for other in matches}) == 1:
            return candidate
    return device.name


if __name__ == "__main__":
    main()
