# Command-line interface

Install the command separately from the library:

```console
pip install "hue-beatsync[cli]"
```

The `cli` extra contains Click and the sounddevice audio backend. Installing
`hue-beatsync` without an extra keeps both out of library-only environments.

## Commands

```text
hue-beatsync [--json | --plain] run <area> [options]
hue-beatsync [--json | --plain] stop <area>
hue-beatsync [--json | --plain] areas list
hue-beatsync [--json | --plain] devices list
hue-beatsync [--json | --plain] visuals list
```

Use `hue-beatsync <command> --help` for the complete option list. Global output
flags come before the command.

Start a stream with the default `pulse` visual:

```console
hue-beatsync run "Music"
```

Select an input by index or by a unique part of its name and stop after a fixed
duration:

```console
hue-beatsync run "Music" --device "Stereo Mix" --visual spectrum --seconds 60
```

List the configured entertainment areas before starting, or explicitly release
one that is active:

```console
hue-beatsync areas list
hue-beatsync stop "Music"
```

`run` owns the stream in the foreground and normally releases it when stopped
with Ctrl+C. `stop` is idempotent and also releases an area left active by an
interrupted or different client.

## Output contract

The default output is intended for people. `--plain` emits stable,
tab-separated records for shell pipelines. Tabs, newlines, and backslashes
inside values are escaped. `--json` emits one compact JSON value with no
formatting whitespace.

Command results are written to stdout. Errors are written to stderr. Successful
commands exit with code `0`, runtime failures with `1`, and invalid command-line
usage with `2`.

### `areas list`

JSON is an array with one compact object per Hue entertainment area. The keys
are `id`, `name`, `active`, and `channels`.

```json
[{"id":"6f8…","name":"Music","active":false,"channels":4}]
```

Plain field order is the same as the documented JSON key order. Human output
shows the name first so it can be copied directly into `run` or `stop`.

### `stop`

Stopping an active area returns its canonical name. Calling it for an already
inactive area succeeds with the same result.

```json
{"status":"stopped","area":"Music"}
```

An unknown area returns the available names as structured JSON on stderr:

```json
{"error":"No entertainment area matches 'Kitchen'. Available: Music, Studio","areas":["Music","Studio"]}
```

### `devices list`

JSON is an array with one object per input. The keys are `index`, `name`,
`sample_rate`, `channels`, and `host_api`.

```console
hue-beatsync --json devices list
```

```json
[{"index":3,"name":"Stereo Mix","sample_rate":48000,"channels":2,"host_api":"WASAPI"}]
```

Plain field order is the same as the documented JSON key order.

### `visuals list`

JSON is an array of accepted visual names. Plain output contains one name per
line.

```json
["spectrum","pulse","sweep"]
```

### `run`

After the Hue entertainment stream and audio input are open, the command emits
one status value and keeps running. JSON contains only `status`, `area`, and
`visual`:

```json
{"status":"running","area":"Music","visual":"pulse"}
```

Plain field order is `status`, `area`, `visual`. A runtime error in JSON mode is
a compact object on stderr:

```json
{"error":"No audio input device found"}
```
