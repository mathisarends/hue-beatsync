# Conventions

## Pydantic

Construct models from a dict with `Model.model_validate(data)`, not `Model(**data)`.
Dict-unpacking into a constructor is hard to read and hides where the data comes
from; `model_validate` states the intent — untrusted/loose dict in, validated
model out.

```python
# yes
return SyncSettings.model_validate(data)

# no
return SyncSettings(**data)
```

Keyword arguments for literal, hand-written values are fine — this is only about
unpacking a dict.

Merge dicts with `|`, not `{**a, **b}`.

Defaults belong in the model as field defaults, not in a parallel dict next to
it (see `ResolvedSettings` in `server/src/server/schemas.py`).

## Imports

In `__init__.py` files, always use relative imports, not absolute ones.

```python
# yes
from .sounddevice import SoundDeviceCapture

# no
from lichtorgel.audio.sounddevice import SoundDeviceCapture
```
