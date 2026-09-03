# hue-beatsync-server

Minimal FastAPI server that owns a single long-running `BeatSync` instance
and exposes it as `start` / `stop` / `status` over HTTP, so the CLI (or
anything else) can drive it without holding the process itself.

```bash
uv run --package hue-beatsync-server uvicorn server.main:app --port 8765
```

## Discovery

`area` and `device` are free-form — an area name or id, a device index or a
fragment of its name. Two read-only routes list the valid choices so a client
can offer a picker instead of guessing:

```bash
curl localhost:8765/areas
curl localhost:8765/devices
```

`/areas` asks the Hue bridge; each entry has `id`, `name`, `channels` and
`active` (already streaming). `/devices` queries the audio backend; each entry
has `index`, `name`, `samplerate`, `channels`, `host_api`, `is_default` (what
you get when `device` is unset) and `supports_exclusive` — the `exclusive`
setting needs a WASAPI device and is rejected on anything else.

Both return `503` with the underlying reason when the bridge or the audio
backend is unreachable.

## Defaults

`POST /start` accepts every field optional. Any field you omit falls back to
a configured default, then to a built-in default (`visual=pulse`, `rate=50`,
`sensitivity=1.2`, `gamma=1.0`, `floor=0.18`, `max_frequency=14000`,
`exclusive=false`, `gain=1.0`).

Configure your own defaults (e.g. your usual area) with `PUT /defaults` —
only the fields you pass are updated, everything else is left as-is:

```bash
curl -X PUT localhost:8765/defaults -H 'content-type: application/json' \
  -d '{"area": "Living Room", "sensitivity": 1.5}'
curl localhost:8765/defaults
curl -X POST localhost:8765/start -H 'content-type: application/json' -d '{}'
```

Defaults are persisted to `lichtorgel.yml` in the repository root. Only the keys
you set are stored; everything else falls back to the built-in defaults in
`ResolvedSettings`.

The checked-in file holds the built-in defaults verbatim:

```yaml
visual: pulse
rate: 50
sensitivity: 1.2
gamma: 1.0
floor: 0.18
max_frequency: 14000.0
exclusive: false
gain: 1.0
```

`area` and `device` have no default and are omitted until you set them.

## Docker

```bash
docker compose up --build
```

Builds `server/Dockerfile` from the repo root (needed since `server/` depends
on the `lichtorgel/` workspace member) and serves on `localhost:8765`. The
repo-root `lichtorgel.yml` is bind-mounted into the container, so defaults
you set via `PUT /defaults` persist back to that file on the host.
