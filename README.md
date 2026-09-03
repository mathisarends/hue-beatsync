# lichtorgel

UV workspace with two members:

- [`lichtorgel/`](lichtorgel/README.md) — the `hue-beatsync` package: audio
  capture, spectral analysis and visual rendering for driving Philips Hue
  entertainment lights from live audio.
- [`server/`](server/README.md) — a minimal FastAPI server that owns a single
  long-running `BeatSync` instance and exposes it as `start` / `stop` /
  `status` over HTTP.

## Development

```powershell
uv sync --dev --extra sounddevice
uv run ruff check .
uv run ruff format --check .
uv run --package hue-beatsync pytest
```
