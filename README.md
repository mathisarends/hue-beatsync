# lichtorgel

Philips Hue lights that dance to whatever your microphone hears. `lichtorgel`
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

## Workspace

UV workspace with two members:

- [`lichtorgel/`](lichtorgel/README.md) — the `lichtorgel` package: audio
  capture, spectral analysis, beat tracking and visual rendering.
- [`server/`](server/README.md) — a minimal FastAPI server that owns a single
  long-running `Lichtorgel` instance and exposes it as `start` / `stop` /
  `status` over HTTP.

## Quick start

You need a Hue bridge with an entertainment area and Hue credentials in the
environment (see the [server README](server/README.md) for the variables).

```powershell
uv sync --all-packages --all-extras
uv run python -m examples.stream_lights --list      # find your audio input
uv run python -m examples.stream_lights --area "Zimmer" --device 20 --mode pulse
```

`--help` lists every option. The one to tune by eye is `--lead`: raise it if the
lights trail the kick, lower it if they jump ahead. See the
[package README](lichtorgel/README.md) for how it works.

## Running the server

```bash
./scripts/serve.sh      # or: .\scripts\serve.ps1
```

Serves on http://127.0.0.1:8765, with the API docs at `/docs`. Audio capture
needs the host's sound stack, so on Windows run it this way rather than in
Docker - see the [server README](server/README.md#audio-in-the-container).

## Development

```powershell
uv sync --dev --all-packages --all-extras
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
