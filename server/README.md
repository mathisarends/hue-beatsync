# hue-beatsync-server

Minimal FastAPI server that owns a single long-running `BeatSync` instance
and exposes it as `start` / `stop` / `status` over HTTP, so the CLI (or
anything else) can drive it without holding the process itself.

```bash
uv run --package hue-beatsync-server uvicorn server.main:app --port 8765
```

`scripts/serve.sh` (Git Bash, WSL, Linux) and `scripts\serve.ps1`
(PowerShell) do the same with the dependencies synced first:

```bash
./scripts/serve.sh                 # http://127.0.0.1:8765
./scripts/serve.sh -p 9000 -r
```

```powershell
.\scripts\serve.ps1
.\scripts\serve.ps1 -Port 9000 -Reload
```

`scripts\serve.cmd` is a double-clickable wrapper around the PowerShell one.
From Git Bash, the PowerShell script needs its own interpreter:
`powershell -ExecutionPolicy Bypass -File scripts/serve.ps1`.

Stop the container first if it is up (`docker compose down`) - it publishes on
`0.0.0.0:8765` and would otherwise keep the port, leaving the browser on the
container's answer. Both scripts check the port and say so instead of failing
on the bind.

Run from a **WSL** shell, the server sees WSL's audio backend, not Windows'.
WSLg bridges the Windows microphone in over PulseAudio, but the machine's
playback - what you actually want the lights to follow - is not among the
inputs, because that needs WASAPI loopback. For that, start the server from
Windows itself. `serve.sh` keeps the WSL environment in `.venv-wsl` so a
checkout on `/mnt/c` can be used from both sides without the two overwriting
each other.

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

Settings are grouped by what they affect: `audio` (where the sound comes from),
`analysis` (how it is turned into levels), and `visual` (how those are painted
onto the lights). `area` sits on its own at the top.

`POST /start` accepts every field optional. Any field you omit falls back to a
configured default, then to the built-in default:

```yaml
audio:
  exclusive: false
  gain: 1.0
analysis:
  sensitivity: 1.2
  gamma: 1.0
  floor: 0.18
  max_frequency: 14000.0
visual:
  mode: pulse
  rate: 50
```

That is exactly the checked-in `lichtorgel.yml` in the repository root, which
is where `PUT /defaults` persists your own defaults. `area` and `audio.device`
have no built-in default and are omitted until you set them.

Only the fields you pass are updated, group by group — everything else is left
as-is:

```bash
curl -X PUT localhost:8765/defaults -H 'content-type: application/json' \
  -d '{"area": "Living Room", "analysis": {"sensitivity": 1.5}}'
curl localhost:8765/defaults
curl -X POST localhost:8765/start -H 'content-type: application/json' \
  -d '{"visual": {"mode": "sweep"}}'
```

The second call keeps the stored area and sensitivity and only swaps the
visual — setting one field of a group never clears the rest of it.

## Docker

```bash
docker compose up --build
```

Builds `server/Dockerfile` from the repo root (needed since `server/` depends
on the `lichtorgel/` workspace member) and serves on `localhost:8765`. The
repo-root `lichtorgel.yml` is bind-mounted into the container, so defaults
you set via `PUT /defaults` persist back to that file on the host.

### Bridge credentials

The container needs the same Hue credentials as a native run. Copy
`.env.example` to `.env` in the repo root and fill it in:

```
HUE_BRIDGE_IP=192.168.1.42
HUE_APP_KEY=...
HUE_CLIENT_KEY=...
```

`compose.yml` passes that file to the container via `env_file`, which
lands the values in the container's environment - hueify reads environment
variables before any `.env` file, so nothing needs to be mounted or copied into
the image (`.env` is in `.dockerignore`).

### Audio in the container

The image ships PortAudio, but a container has no sound hardware of its own.
Without one, PortAudio comes up reporting ALSA with zero devices: `/devices`
answers `503` and `/start` has nothing to capture.

On a **Linux host**, hand the host's sound devices to the container by
uncommenting the `devices:` and `group_add:` lines in `compose.yml`.

On **Windows and macOS** there is nothing to pass through. Docker runs Linux
containers inside a VM that has no `/dev/snd` and no audio backend, so no bind
mount or `--device` flag can reach the host's sound stack. Beyond that, the
sound you want to react to is what the machine is *playing*, which on Windows
means WASAPI loopback - a Windows API that a Linux container cannot call at
all. Run the server natively there (`scripts\serve.ps1`) and keep the image
for deploying to a Linux box with a sound card attached.
