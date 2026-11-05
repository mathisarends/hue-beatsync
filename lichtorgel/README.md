# lichtorgel

`lichtorgel` turns live audio input into frames for a Philips Hue
entertainment area. With Hue credentials in the environment, the complete
workflow is:

```python
import asyncio

from lichtorgel import Lichtorgel


async def main() -> None:
    async with Lichtorgel("Musikbereich") as lichtorgel:
        await lichtorgel.run()


asyncio.run(main())
```

Pass `device`, `mode`, `rate`, `sensitivity`, `gamma`, `floor`, `lead`, or
`max_frequency` only when their defaults need changing. `Lichtorgel` creates and
closes the Hue client, entertainment stream, and audio capture inside its
context manager.

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
about three seconds, `lichtorgel` follows its tempo and fires each flash
`lead` seconds before the kick is due, falling back to reacting whenever the
beat gets lost. The right `lead` depends on the room. Watch a track with a
plain kick: raise `lead` if the lights trail the kick, lower it if they jump
ahead.

```powershell
uv run python -m examples.stream_lights --area "Musikbereich" --lead 0.12
```

Audio capture, spectral analysis and visual rendering remain independently
available for applications that need lower-level control.

Install the system-audio backend only when it is needed:

```powershell
pip install "lichtorgel[sounddevice]"
```

```python
from lichtorgel import SoundDeviceCapture, SpectralAnalyzer, resolve_device

device = resolve_device("Microphone")
analyzer = SpectralAnalyzer(device.samplerate)

with SoundDeviceCapture(device, analyzer.feed):
    features = analyzer.features
```

The public package contains only reusable logic:

- `analysis.py` extracts normalized bands, energy, beats, tempo, and how
  percussive the material is at all, which lets the visuals stay calm on music
  that has no beat to follow.
- `audio/ports.py` defines the capture contract implemented by interchangeable
  backends without depending on a particular input library.
- `audio/sounddevice.py` discovers system inputs and streams mono blocks from them.
- `visuals.py` maps the latest analysis snapshot onto Hue frames.
- `smoothing.py` contains the time-based filters used by analysis and visuals.

## Examples

The executable wrapper lives in `examples/`:

```powershell
uv run python -m examples.stream_lights --area "Musikbereich" --mode pulse
```

Available visual names are returned by `visual_names()`. Construct them through
`create_visual()` so applications do not depend on internal registries.

## Development

```powershell
uv sync --dev --all-packages --all-extras
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
