import yaml

from server.defaults import YmlDefaultsStore
from server.schemas import AnalysisSettings, AudioSettings, SyncSettings, VisualSettings


def test_missing_file_resolves_to_builtin_defaults(tmp_path) -> None:
    store = YmlDefaultsStore(tmp_path / "missing.yml")

    resolved = store.resolve(SyncSettings())

    assert store.current == SyncSettings()
    assert resolved.area is None
    assert resolved.audio.gain == 1.0
    assert resolved.analysis.sensitivity == 1.2
    assert resolved.visual.mode == "pulse"


def test_request_values_override_configured_defaults_by_group(tmp_path) -> None:
    path = tmp_path / "defaults.yml"
    path.write_text(
        yaml.safe_dump(
            {
                "area": "Living Room",
                "audio": {"device": 3, "gain": 1.4},
                "analysis": {"sensitivity": 1.5, "gamma": 0.9},
                "visual": {"mode": "pulse", "rate": 50},
            }
        )
    )
    store = YmlDefaultsStore(path)

    resolved = store.resolve(
        SyncSettings(
            audio=AudioSettings(gain=2.0),
            analysis=AnalysisSettings(gamma=1.1),
            visual=VisualSettings(rate=30),
        )
    )

    assert resolved.area == "Living Room"
    assert resolved.audio.device == 3
    assert resolved.audio.gain == 2.0
    assert resolved.analysis.sensitivity == 1.5
    assert resolved.analysis.gamma == 1.1
    assert resolved.visual.mode == "pulse"
    assert resolved.visual.rate == 30


def test_update_preserves_unspecified_values_and_persists_result(tmp_path) -> None:
    path = tmp_path / "config" / "defaults.yml"
    store = YmlDefaultsStore(path)
    store.update(
        SyncSettings(
            area="Living Room",
            analysis=AnalysisSettings(sensitivity=1.5, gamma=0.9),
        )
    )

    updated = store.update(SyncSettings(analysis=AnalysisSettings(gamma=1.1)))
    reloaded = YmlDefaultsStore(path)

    assert updated.area == "Living Room"
    assert updated.analysis.sensitivity == 1.5
    assert updated.analysis.gamma == 1.1
    assert reloaded.current == updated
