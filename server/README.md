# hue-beatsync-server

Minimal FastAPI server that owns a single long-running `BeatSync` instance
and exposes it as `start` / `stop` / `status` over HTTP, so the CLI (or
anything else) can drive it without holding the process itself.

```bash
uv run --package hue-beatsync-server uvicorn server.main:app --port 8765
```

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

Defaults are persisted to `~/.hue-beatsync/lichtorgel.yaml`.
