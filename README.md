# hue-beatsync

`hue-beatsync` turns live microphone input into frames for a Philips Hue
entertainment area. The library separates audio capture, spectral analysis and
visual rendering so each part can also be used independently.

```python
from hue_beatsync import AudioCapture, SpectralAnalyzer, resolve_device

device = resolve_device("Microphone")
analyzer = SpectralAnalyzer(device.samplerate)

with AudioCapture(device, analyzer.feed):
    features = analyzer.features
```

The public package contains only reusable logic:

- `analysis.py` extracts normalized bands, energy, beats and tempo.
- `audio.py` discovers inputs and streams mono blocks from a microphone.
- `visuals.py` maps the latest analysis snapshot onto Hue frames.
- `smoothing.py` contains the time-based filters used by analysis and visuals.

## Examples

The executable workflows live in `examples/` and are intentionally outside the
package:

```powershell
uv run python -m examples.inspect_audio --list
uv run python -m examples.inspect_audio
uv run python -m examples.stream_lights --area "Musikbereich" --mode pulse
uv run python -m examples.simulate
```

`compare_inputs.py` compares microphones and `record_audio.py` writes a WAV file
with a signal-quality report. Start with `inspect_audio.py` before connecting to
a bridge; it makes microphone and beat-detection problems visible immediately.

Available visual names are returned by `visual_names()`. Construct them through
`create_visual()` so applications do not depend on internal registries.

## Development

```powershell
uv sync --dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
