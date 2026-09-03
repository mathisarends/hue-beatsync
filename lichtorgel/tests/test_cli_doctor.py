import json

from click.testing import CliRunner

from hue_beatsync.audio import AudioDevice
from hue_beatsync.cli import command, doctor_command
from hue_beatsync.diagnostics import AudioDiagnostic


def diagnostic():
    return AudioDiagnostic(
        device=AudioDevice(2, "Loopback", 48_000, 2, "WASAPI"),
        duration=1.0,
        audio_detected=True,
        beats=4,
        bpm=120.0,
        dropouts=0,
        latency_ms=12.5,
        max_loudness=0.04,
        max_energy=0.8,
        max_percussiveness=0.6,
        levels=(0.2, 0.4, 0.6, 0.8, 1.0),
    )


def test_doctor_returns_one_compact_json_result(monkeypatch):
    async def diagnose(*_args, **_settings):
        return diagnostic()

    monkeypatch.setattr(doctor_command, "diagnose_audio", diagnose)

    result = CliRunner().invoke(command(), ["doctor", "--seconds", "1", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["device"] == {"index": 2, "name": "Loopback"}
    assert data["bpm"] == 120.0
    assert data["features"]["bands"]["treble"] == 1.0
    assert result.stdout.count("\n") == 1


def test_global_json_flag_works_after_nested_command(monkeypatch):
    async def available():
        return []

    from hue_beatsync.cli import area_commands

    monkeypatch.setattr(area_commands, "list_areas", available)

    result = CliRunner().invoke(command(), ["areas", "list", "--json"])

    assert result.exit_code == 0
    assert result.stdout == "[]\n"
