# `lichtorgel` CLI

A single Go binary that drives the [server](../server/README.md) over HTTP. Every
command prints a readable summary for a person, or stable JSON with `--json` for
a script or an agent.

## Build

```bash
cd cli
go build -o bin/lichtorgel ./cmd/lichtorgel
```

## Pointing it at a server

`http://127.0.0.1:8765` unless told otherwise. In precedence order:

1. `--api-url http://host:port`
2. `LICHTORGEL_API_URL` in the environment
3. `LICHTORGEL_API_URL` (or `LICHTORGEL_PORT`) in the dotenv file named by
   `--env-file`, which defaults to `.env` in the working directory

## First run

```bash
lichtorgel setup     # pick an area and an audio input, save both
lichtorgel doctor    # confirm the server reaches the bridge and the sound card
lichtorgel start
lichtorgel stop
```

`setup` is a wizard. The two settings it saves are also available on their own:

```bash
lichtorgel area                       # list the bridge's entertainment areas
lichtorgel area select "Living Room"  # save one (asks when the name is omitted)
lichtorgel device                     # list the audio inputs
lichtorgel device select 15           # save one, by index or by part of its name
lichtorgel device select 15 --by-index
```

`area select` and `device select` write to the server's `PUT /defaults`, which
persists to `lichtorgel.yml` — the same file a hand edit would touch. The name is
saved rather than the index, because audio backends renumber their devices as
soon as the hardware changes; `--by-index` overrides that.

## Streaming

```bash
lichtorgel start
lichtorgel start --area Bedroom --mode sweep --rate 60
lichtorgel status
lichtorgel stop
```

Every setting is a flag on `start`, and a flag wins over the saved default for
that one run. A setting you do not pass is never sent, so it cannot overwrite
what is stored.

| Flag | Meaning |
| --- | --- |
| `--area` | Hue entertainment area, by name or id |
| `--device` | Audio input, by index or part of its name |
| `--[no-]exclusive` | Take the input exclusively; WASAPI only |
| `--gain` | Multiply the captured signal before analysis |
| `--sensitivity` | How readily quiet passages still reach the lights |
| `--gamma` | Curve applied to the levels; above 1 darkens the middle |
| `--floor` | Level below which a band counts as silent |
| `--max-frequency` | Highest frequency the spectrum covers, in Hz |
| `--mode` | `spectrum`, `pulse` or `sweep` |
| `--rate` | Frames sent to the bridge per second |

## Defaults

```bash
lichtorgel defaults                       # show what is saved
lichtorgel defaults set --mode sweep --sensitivity 1.5
```

`defaults show` prints only what has actually been saved. Anything absent falls
back to the server's built-in value.

## JSON

```bash
lichtorgel status --json
lichtorgel device list --fields index,name --compact
```

`--fields` selects top-level keys and implies `--json`; naming a key that does
not exist fails with the list of keys that do. `--compact` drops the
indentation. Errors go to stderr in the same shape:

```json
{
  "error": {
    "code": "conflict",
    "message": "already streaming to 'Bedroom'",
    "hint": "Run: lichtorgel status",
    "status": 409
  }
}
```

Anything that would otherwise ask a question refuses under `--json` instead of
blocking, and says what to pass.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | The server answered with a failure, or `doctor` found one |
| 2 | The command itself was wrong: bad flag, unknown area, nothing to save |

## Regenerating the API client

`internal/client` is generated from the server's own OpenAPI document and is not
edited by hand:

```bash
uv run --package hue-beatsync-server python scripts/export_openapi.py
cd cli && go generate ./...
```

## Development

```bash
cd cli
./scripts/format.sh
./scripts/lint.sh     # golangci-lint, go vet, go test -race
```
