# lichtorgel

UV workspace with two members:

- [`lichtorgel/`](lichtorgel/README.md) — the `lichtorgel` package: audio
  capture, spectral analysis and visual rendering for driving Philips Hue
  entertainment lights from live audio.
- [`server/`](server/README.md) — a minimal FastAPI server that owns a single
  long-running `Lichtorgel` instance and exposes it as `start` / `stop` /
  `status` over HTTP.

## Running the server

```bash
./scripts/serve.sh      # or: .\scripts\serve.ps1
```

Serves on http://127.0.0.1:8765. Audio capture needs the host's sound stack, so
on Windows run it this way rather than in Docker - see the
[server README](server/README.md#audio-in-the-container).

## Running the lights directly

Without the server, the example script streams straight from an audio input:

```powershell
uv run python -m examples.stream_lights --area "Zimmer" --lead 0.1
```

Run it with `--help` for every option.

## Development

```powershell
uv sync --dev --all-packages --all-extras
uv run ruff check .
uv run ruff format --check .
uv run --package lichtorgel pytest
```
