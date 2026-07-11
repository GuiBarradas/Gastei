"""Loaders for YAML seed files — categories, rules, examples.

The YAML files under ``seeds/`` are the canonical source of truth as
documentation; loaders here parse them into validated Pydantic DTOs. When
the application needs the data (Alembic migrations, bootstrap jobs), use
these loaders rather than re-parsing the YAML inline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter, ValidationError

from gastei.schemas.rule import Rule

_RULES_ADAPTER = TypeAdapter(list[Rule])


def load_rules_from_yaml(path: str | Path) -> list[Rule]:
    """Load ``seeds/rules.yaml`` (or a compatible file) into ``list[Rule]``.

    Expected format::

        rules:
          - pattern: "ifood"
            pattern_type: "substring"
            category: "alimentacao.delivery"
            priority: 100  # optional
            enabled: true  # optional

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the YAML is malformed or missing the ``rules`` key.
        ValueError (wrapping ``pydantic.ValidationError``): if any item fails schema validation.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Rules seed not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "rules" not in raw:
        raise ValueError(f"Invalid YAML at {path}: expected a mapping with a 'rules' key")

    items: Any = raw["rules"]
    if not isinstance(items, list):
        raise ValueError(f"Invalid YAML at {path}: 'rules' must be a list")

    try:
        return _RULES_ADAPTER.validate_python(items)
    except ValidationError as exc:
        raise ValueError(f"Invalid rule in {path}: {exc}") from exc
