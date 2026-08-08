import argparse
import math
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sounddevice as sd

from examples.console import bar
from hue_beatsync.audio.sounddevice import AudioDevice, resolve_device

_WINDOW = 2048
_SILENT_FLOOR = -90.0


@dataclass(frozen=True, slots=True)
class Recording:
    device: AudioDevice
    samples: np.ndarray

    @property
    def peak(self) -> float:
        return float(np.max(np.abs(self.samples))) if self.samples.size else 0.0

    @property
    def rms(self) -> float:
        return (
            float(np.sqrt(np.mean(np.square(self.samples))))
            if self.samples.size
            else 0.0
        )

    @property
    def clipped(self) -> int:
        return int(np.count_nonzero(np.abs(self.samples) >= 0.999))

    @property
    def digital_silence(self) -> float:
        """The share of samples that are exactly zero.

        This is the most telling number here. Analogue hardware always brings
        some noise with it and physically cannot produce an exact zero, so a
        high share means something downstream is replacing the signal: a noise
        gate, a suppression filter, or Windows denying microphone access.
        """
        if not self.samples.size:
            return 1.0
        return float(np.count_nonzero(self.samples == 0.0) / self.samples.size)

    @property
    def flatness(self) -> float:
        """Spectral flatness: near 0 is tonal, near 1 is featureless noise."""
        spectra = [
            np.abs(
                np.fft.rfft(self.samples[start : start + _WINDOW] * np.hanning(_WINDOW))
            )
            for start in range(0, len(self.samples) - _WINDOW, _WINDOW)
        ]
        if not spectra:
            return 1.0
        average = np.mean(spectra, axis=0)[1:]
        average = np.maximum(average, 1e-12)
        geometric = float(np.exp(np.mean(np.log(average))))
        return geometric / float(np.mean(average))

    @property
    def verdict(self) -> str:
        if self.digital_silence > 0.99:
            return "pure digital silence - Windows is not letting this input through"
        if self.digital_silence > 0.4:
            return "mostly digital silence - a noise gate is cutting the signal away"
        if dbfs(self.rms) < -60:
            return "nothing is arriving - the input is muted, or turned down to zero"
        if self.flatness > 0.5:
            return "loud but featureless - this is the noise floor, not the room"
        if dbfs(self.rms) < -40:
            return "very weak, but it is hearing something real"
        return "healthy signal"


def dbfs(amplitude: float) -> float:
    return (
        _SILENT_FLOOR
        if amplitude <= 0
        else max(20 * math.log10(amplitude), _SILENT_FLOOR)
    )


def capture(device: AudioDevice, seconds: float, label: str) -> Recording:
    """Record while drawing a live meter, so a dead input is obvious at once."""
    channels = min(device.channels, 2)
    collected: list[np.ndarray] = []

    with sd.InputStream(
        device=device.index,
        channels=channels,
        samplerate=device.samplerate,
        blocksize=1024,
        dtype="float32",
        callback=lambda data, *_: collected.append(data.copy()),
    ):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            time.sleep(0.05)
            recent = collected[-8:]
            level = float(np.max(np.abs(np.concatenate(recent)))) if recent else 0.0
            remaining = deadline - time.monotonic()
            print(
                f"\r  {label} {remaining:4.1f}s  {bar(_meter(level), 24)} "
                f"{dbfs(level):>6.1f} dBFS  ",
                end="",
                flush=True,
            )

    print()
    if not collected:
        return Recording(device, np.zeros(0, dtype=np.float32))
    return Recording(device, np.concatenate(collected).mean(axis=1))


def _meter(level: float) -> float:
    """Map -60..0 dBFS onto a bar, since amplitude alone shows almost nothing."""
    return max(0.0, min((dbfs(level) + 60) / 60, 1.0))


def write_wav(recording: Recording, path: Path) -> None:
    scaled = np.clip(recording.samples, -1.0, 1.0) * 32767
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(recording.device.samplerate)
        handle.writeframes(scaled.astype("<i2").tobytes())


def report(recording: Recording) -> None:
    print(f"  peak      {dbfs(recording.peak):>7.1f} dBFS")
    print(f"  rms       {dbfs(recording.rms):>7.1f} dBFS")
    print(f"  silence   {recording.digital_silence:>7.1%}   exactly zero samples")
    print(f"  flatness  {recording.flatness:>7.2f}   (0 tonal, 1 noise)")
    if recording.clipped:
        print(f"  clipped   {recording.clipped:>7} samples - turn the input down")
    print(f"  -> {recording.verdict}")

    if recording.digital_silence > 0.4:
        print()
        print("  A gate this aggressive is Windows signal processing, not the mic.")
        print("  Sound settings -> the device -> turn off audio enhancements, or")
        print("  try the same microphone through a different host API: the WDM-KS")
        print("  entries bypass the Windows processing chain entirely.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record microphone input and report absolute signal quality."
    )
    parser.add_argument("--device", help="input device index or part of its name")
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--out", type=Path, default=Path("recording.wav"))
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="record silence first, then music, and compare the two",
    )
    args = parser.parse_args()

    device = resolve_device(args.device)
    print(f"Recording from {device}\n")

    if not args.baseline:
        recording = capture(device, args.seconds, "recording")
        write_wav(recording, args.out)
        print()
        report(recording)
        print(f"\nWritten to {args.out.resolve()} - play it and listen.")
        return

    input("Make the room quiet, then press Enter...")
    quiet = capture(device, args.seconds, "silence  ")
    print()
    report(quiet)

    input("\nNow start the music, loud, then press Enter...")
    loud = capture(device, args.seconds, "music    ")
    write_wav(loud, args.out)
    print()
    report(loud)

    difference = dbfs(loud.rms) - dbfs(quiet.rms)
    print(f"\nMusic is {difference:+.1f} dB against silence.")
    if difference < 3:
        print("The microphone does not react to the music at all. That is a Windows")
        print("problem, not an audio one: the input is muted, its level is at zero,")
        print("or microphone access is denied and Windows is feeding silence.")
    elif difference < 12:
        print("It reacts, but barely. Raise the input level in the sound settings.")
    else:
        print("It clearly hears the music. Any remaining trouble is in the mapping.")
    print(f"\nWritten to {args.out.resolve()} - play it and listen.")


if __name__ == "__main__":
    main()
