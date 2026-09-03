from pathlib import Path
from typing import Any

import yaml

from server.configuration.base import DefaultsStore
from server.schemas import ResolvedSettings, SyncSettings

# yml_store.py lives at <repo>/server/src/server/configuration/, so the
# repo root is five levels up.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULTS_PATH = _REPO_ROOT / "lichtorgel.yml"


class YmlDefaultsStore(DefaultsStore):
    """DefaultsStore backed by a YAML file on disk."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULTS_PATH
        self._defaults = self._load()

    @property
    def current(self) -> SyncSettings:
        return self._defaults

    def update(self, changes: SyncSettings) -> SyncSettings:
        self._defaults = SyncSettings.model_validate(
            _layer(_provided(self._defaults), _provided(changes))
        )
        self._save()
        return self._defaults

    def resolve(self, request: SyncSettings) -> ResolvedSettings:
        return ResolvedSettings.model_validate(
            _layer(_provided(self._defaults), _provided(request))
        )

    def _load(self) -> SyncSettings:
        if not self._path.exists():
            return SyncSettings()
        data = yaml.safe_load(self._path.read_text()) or {}
        return SyncSettings.model_validate(data)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = _provided(self._defaults)
        self._path.write_text(yaml.safe_dump(data, sort_keys=False))


def _provided(settings: SyncSettings) -> dict[str, Any]:
    """The fields a caller actually filled in. Every SyncSettings field
    defaults to None, so dropping the Nones - and any group left empty by
    that - leaves exactly those."""
    data = settings.model_dump(exclude_none=True)
    return {key: value for key, value in data.items() if value != {}}


def _layer(base: dict[str, Any], top: dict[str, Any]) -> dict[str, Any]:
    """Merge `top` over `base`, group by group. A plain `base | top` would
    let a request that sets one field of a group drop the rest of it."""
    merged = base | top
    for key, value in top.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _layer(base[key], value)
    return merged
