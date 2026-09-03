import json

from click.testing import CliRunner

from hue_beatsync.audio import AudioDevice
from hue_beatsync.cli import app


def test_devices_list_has_compact_stable_json(monkeypatch):
    device = AudioDevice(3, "Stereo Mix", 48_000, 2, "WASAPI")
    monkeypatch.setattr(app, "input_devices", lambda: [device])

    result = CliRunner().invoke(app.cli, ["--json", "devices", "list"])

    assert result.exit_code == 0
    assert result.output == (
        '[{"index":3,"name":"Stereo Mix","sample_rate":48000,'
        '"channels":2,"host_api":"WASAPI"}]\n'
    )


def test_visuals_list_supports_plain_lines(monkeypatch):
    monkeypatch.setattr(app, "visual_names", lambda: ("pulse", "spectrum"))

    result = CliRunner().invoke(app.cli, ["--plain", "visuals", "list"])

    assert result.exit_code == 0
    assert result.output == "pulse\nspectrum\n"


def test_output_modes_are_mutually_exclusive():
    result = CliRunner().invoke(app.cli, ["--json", "--plain", "devices", "list"])

    assert result.exit_code == 2
    assert "--json and --plain cannot be used together" in result.output


def test_run_reports_started_state(monkeypatch):
    events = []

    class Sync:
        mode = "pulse"

        def __init__(self, area, **settings):
            events.append(("created", area, settings))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        async def run(self, seconds):
            events.append(("ran", seconds))

    monkeypatch.setattr(app, "BeatSync", Sync)

    result = CliRunner().invoke(app.cli, ["--json", "run", "Music", "--seconds", "1.5"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "status": "running",
        "area": "Music",
        "visual": "pulse",
    }
    assert events[-1] == ("ran", 1.5)


def test_runtime_errors_are_json_on_stderr(monkeypatch):
    monkeypatch.setattr(
        app, "input_devices", lambda: (_ for _ in ()).throw(RuntimeError("no input"))
    )

    result = CliRunner().invoke(app.cli, ["--json", "devices", "list"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {"error": "no input"}
