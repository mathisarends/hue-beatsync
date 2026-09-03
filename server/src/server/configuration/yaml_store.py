from pathlib import Path
from typing import Any

import yaml

from server.configuration.base import DefaultsStore
from server.schemas import SyncSettings

_DEFAULTS_PATH = Path.home() / ".hue-beatsync" / "lichtorgel.yaml"

_HARD_DEFAULTS: dict[str, Any] = {
    "visual": "pulse",
    "rate": 50,
    "sensitivity": 1.2,
    "gamma": 1.0,
    "floor": 0.18,
    "max_frequency": 14_000.0,
    "exclusive": False,
    "gain": 1.0,
}


class YamlDefaultsStore(DefaultsStore):
    """DefaultsStore backed by a YAML file on disk."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULTS_PATH
        self._defaults = self._load()

    @property
    def current(self) -> SyncSettings:
        return self._defaults

    def update(self, changes: SyncSettings) -> SyncSettings:
        merged = {
            **self._defaults.model_dump(exclude_none=True),
            **changes.model_dump(exclude_unset=True, exclude_none=True),
        }
        self._defaults = SyncSettings(**merged)
        self._save()
        return self._defaults

    def resolve(self, request: SyncSettings) -> dict[str, Any]:
        return {
            **_HARD_DEFAULTS,
            **self._defaults.model_dump(exclude_none=True),
            **request.model_dump(exclude_unset=True, exclude_none=True),
        }

    def _load(self) -> SyncSettings:
        if not self._path.exists():
            return SyncSettings()
        data = yaml.safe_load(self._path.read_text()) or {}
        return SyncSettings(**data)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = self._defaults.model_dump(exclude_none=True)
        self._path.write_text(yaml.safe_dump(data, sort_keys=False))
