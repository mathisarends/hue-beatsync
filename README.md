# lichtorgel

UV workspace with two members:

- [`lichtorgel/`](lichtorgel/README.md) — the `hue-beatsync` package: audio
  capture, spectral analysis and visual rendering for driving Philips Hue
  entertainment lights from live audio.
- [`server/`](server/README.md) — a minimal FastAPI server that owns a single
  long-running `BeatSync` instance and exposes it as `start` / `stop` /
  `status` over HTTP.

## Running the server

```bash
./scripts/serve.sh      # or: .\scripts\serve.ps1
```

Serves on http://127.0.0.1:8765. Audio capture needs the host's sound stack, so
on Windows run it this way rather than in Docker - see the
[server README](server/README.md#audio-in-the-container).

## Development

```powershell
uv sync --dev --extra sounddevice
uv run ruff check .
uv run ruff format --check .
uv run --package hue-beatsync pytest
```
