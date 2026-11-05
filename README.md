# hue-beatsync

Philips Hue lights that dance to whatever your microphone hears. hue-beatsync
listens to live audio, finds the beat, and streams frames to a Hue
entertainment area over the low-latency DTLS entertainment API, built on
[hueify](https://github.com/mathisarends/hueify).

- **On the beat.** A beat tracker follows tempo and phase, so each flash fires
  slightly *ahead* of the kick and lands with it, instead of trailing it by the
  tenth of a second the microphone, bridge and lamps add up to.
- **Disco or ambient, by track.** Steady drums hit hard: the room goes dark
  between kicks and the color cuts with each one. Pads and ambient material
  glide softly instead.
- **Three light shows:** `spectrum`, `pulse` and `sweep`.

## Quick start

You need a Hue bridge with an entertainment area and Hue credentials in the
environment (see the [server README](hue_beatsync/server/README.md) for the
variables).

```powershell
uv sync --all-extras
uv run python -m examples.stream_lights --list      # find your audio input
uv run python -m examples.stream_lights --area "Zimmer" --device 20 --mode pulse
```

`--help` lists every option. The one to tune by eye is `--lead`: raise it if the
lights trail the kick, lower it if they jump ahead.

## Layout

One flat package, `hue_beatsync/`:

- `analysis.py` extracts normalized bands, energy, beats, tempo, and how
  percussive the material is at all, which lets the visuals stay calm on music
  that has no beat to follow.
- `tempo.py` follows the beat grid so a beat can be acted on before it lands.
- `audio/ports.py` defines the capture contract implemented by interchangeable
  backends without depending on a particular input library.
- `audio/sounddevice.py` discovers system inputs and streams mono blocks from them.
- `visuals.py` maps the latest analysis snapshot onto Hue frames.
- `smoothing.py` contains the time-based filters used by analysis and visuals.
- `beatsync.py` ties it all together: capture, analysis, visuals and the Hue
  stream behind one context manager.
- `server/` is a small FastAPI server that owns one running `BeatSync` and
  exposes it as `start` / `stop` / `status` over HTTP, see the
  [server README](hue_beatsync/server/README.md).

## Using it from Python

```python
import asyncio

from hue_beatsync import BeatSync


async def main() -> None:
    async with BeatSync("Musikbereich") as beatsync:
        await beatsync.run()


asyncio.run(main())
```

Pass `device`, `mode`, `rate`, `sensitivity`, `gamma`, `floor`, `lead`, or
`max_frequency` only when their defaults need changing. `BeatSync` creates and
closes the Hue client, entertainment stream, and audio capture inside its
context manager. The system-audio backend is an optional extra:

```powershell
pip install "hue-beatsync[sounddevice]"
```

Audio capture, spectral analysis and visual rendering are also available on
their own:

```python
from hue_beatsync import SoundDeviceCapture, SpectralAnalyzer, resolve_device

device = resolve_device("Microphone")
analyzer = SpectralAnalyzer(device.samplerate)

with SoundDeviceCapture(device, analyzer.feed):
    features = analyzer.features
```

Available visual names are returned by `visual_names()`. Construct them through
`create_visual()` so applications do not depend on internal registries.

## How the lights react

Two settings decide how the room reads. `floor` is the brightness the lamps
never fall below while ambient material is playing, so a quiet passage stays
visible instead of reading as off; silence settles into a still dimmer glow.
`gamma` above 1 restores contrast if the result looks too flat.

How hard the lights hit follows how percussive the music is. On a steady beat
the floor drops, the room goes dark between kicks, each flash lands at full
strength in the frame its beat arrives in, and the color cuts with it. On
ambient material the lights glide between colors and none of that applies.
On Windows the stream also asks for a 1 ms system timer while it runs, so
frames leave on time instead of up to 17 ms late.

Reacting to a kick always lands late: the microphone, the bridge and the lamps
add up to about a tenth of a second. So once a steady beat has played for
about three seconds, hue-beatsync follows its tempo and fires each flash
`lead` seconds before the kick is due, falling back to reacting whenever the
beat gets lost. The right `lead` depends on the room. Watch a track with a
plain kick: raise `lead` if the lights trail the kick, lower it if they jump
ahead.

## Running the server

```bash
./scripts/serve.sh      # or: .\scripts\serve.ps1
```

Serves on http://127.0.0.1:8765, with the API docs at `/docs`. Audio capture
needs the host's sound stack, so on Windows run it this way rather than in
Docker - see the
[server README](hue_beatsync/server/README.md#audio-in-the-container).

## Development

```powershell
uv sync --dev --all-extras
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
