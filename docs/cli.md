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

## Output contract

The default output is intended for people. `--plain` emits stable,
tab-separated records for shell pipelines. Tabs, newlines, and backslashes
inside values are escaped. `--json` emits one compact JSON value with no
formatting whitespace.

Command results are written to stdout. Errors are written to stderr. Successful
commands exit with code `0`, runtime failures with `1`, and invalid command-line
usage with `2`.

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
