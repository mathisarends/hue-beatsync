# lichtorgel

UV workspace with two members:

- [`lichtorgel/`](lichtorgel/README.md) — the `lichtorgel` package: audio
  capture, spectral analysis and visual rendering for driving Philips Hue
  entertainment lights from live audio.
- [`server/`](server/README.md) — a minimal FastAPI server that owns a single
  long-running `Lichtorgel` instance and exposes it as `start` / `stop` /
  `status` over HTTP.

Plus [`cli/`](docs/cli.md), a Go binary that drives that server from the
terminal.

## Running the server

```bash
./scripts/serve.sh      # or: .\scripts\serve.ps1
```

Serves on http://127.0.0.1:8765. Audio capture needs the host's sound stack, so
on Windows run it this way rather than in Docker - see the
[server README](server/README.md#audio-in-the-container).

## Using the CLI

```bash
cd cli && go build -o bin/lichtorgel ./cmd/lichtorgel

./bin/lichtorgel setup     # pick an area and an audio input, save both
./bin/lichtorgel doctor
./bin/lichtorgel start
```

Every command also speaks JSON (`--json`, `--fields`), so agents and scripts get
the same surface a person does. See [`docs/cli.md`](docs/cli.md).

## Development

```powershell
uv sync --dev --extra sounddevice
uv run ruff check .
uv run ruff format --check .
uv run --package lichtorgel pytest
```
