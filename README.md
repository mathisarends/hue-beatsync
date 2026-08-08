# hue-beatsync

`hue-beatsync` turns live audio input into frames for a Philips Hue
entertainment area. With Hue credentials in the environment, the complete
workflow is:

```python
import asyncio

from hue_beatsync import BeatSync

asyncio.run(BeatSync("Musikbereich").run())
```

Pass `device`, `mode`, `rate`, `sensitivity`, `gamma`, or `max_frequency` only
when their defaults need changing. An existing `Hueify` client can be supplied
as `hue=client`; otherwise `BeatSync` creates and closes one for the run.

Audio capture, spectral analysis and visual rendering remain independently
available for applications that need lower-level control.

Install the system-audio backend only when it is needed:

```powershell
pip install "hue-beatsync[sounddevice]"
```

```python
from hue_beatsync import SoundDeviceCapture, SpectralAnalyzer, resolve_device

device = resolve_device("Microphone")
analyzer = SpectralAnalyzer(device.samplerate)

with SoundDeviceCapture(device, analyzer.feed):
    features = analyzer.features
```

The public package contains only reusable logic:

- `analysis.py` extracts normalized bands, energy, beats and tempo.
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
uv sync --dev --extra sounddevice
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
