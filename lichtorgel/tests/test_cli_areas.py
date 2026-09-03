import json

from click.testing import CliRunner

from hue_beatsync.areas import AreaNotFoundError, BeatSyncArea
from hue_beatsync.cli import area_commands, command


def test_areas_list_has_compact_json(monkeypatch):
    async def available():
        return [BeatSyncArea("area-id", "Music", True, 4)]

    monkeypatch.setattr(area_commands, "list_areas", available)

    result = CliRunner().invoke(command(), ["--json", "areas", "list"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [
        {"id": "area-id", "name": "Music", "active": True, "channels": 4}
    ]


def test_stop_releases_area(monkeypatch):
    async def stop(_wanted):
        return BeatSyncArea("area-id", "Music", False, 4)

    monkeypatch.setattr(area_commands, "stop_area", stop)

    result = CliRunner().invoke(command(), ["--json", "stop", "Music"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"status": "stopped", "area": "Music"}


def test_unknown_area_returns_names_as_structured_error(monkeypatch):
    async def stop(_wanted):
        raise AreaNotFoundError("Kitchen", ("Music", "Studio"))

    monkeypatch.setattr(area_commands, "stop_area", stop)

    result = CliRunner().invoke(command(), ["--json", "stop", "Kitchen"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": "No entertainment area matches 'Kitchen'. Available: Music, Studio",
        "areas": ["Music", "Studio"],
    }
