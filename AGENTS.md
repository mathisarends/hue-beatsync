# Repository coding guidelines

- Do not add module-level docstrings.
- Do not add `from __future__ import annotations` by default. Use it only when a
  concrete typing requirement cannot be expressed clearly without it.
- Relative imports within the package are allowed. Keep imports consistent and
  avoid relying on repository-root import side effects.
- Prefix names with `_` only when they are private to their defining module.
  Names imported by another module are part of the defining module's public API
  and must not have an underscore prefix.
- Keep the package-level API explicit through `hue_beatsync.__init__`. A name may
  be public in a submodule without being re-exported at package level.
- Keep public interfaces above private implementation details where practical.
- Comments document architectural decisions, constraints, or information that
  cannot be expressed in code. Do not narrate the code or add documentation by
  default.
- Commit completed changes in small, coherent steps when working across multiple
  concerns.
