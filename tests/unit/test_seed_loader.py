"""Specs for the YAML rules loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from gastei.utils.seed_loader import load_rules_from_yaml

pytestmark = pytest.mark.unit


def _write(tmp: Path, body: str) -> Path:
    f = tmp / "rules.yaml"
    f.write_text(body, encoding="utf-8")
    return f


def test_loads_minimal_valid_file(tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        """
rules:
  - { pattern: "ifood", pattern_type: "substring", category: "alimentacao.delivery" }
""",
    )
    rules = load_rules_from_yaml(f)
    assert len(rules) == 1
    assert rules[0].pattern == "ifood"
    assert rules[0].pattern_type == "substring"
    assert rules[0].category == "alimentacao.delivery"
    assert rules[0].priority == 100  # default
    assert rules[0].enabled is True  # default


def test_loads_full_fields(tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        """
rules:
  - pattern: "uber"
    pattern_type: "regex"
    category: "transporte.app"
    priority: 200
    enabled: false
""",
    )
    rules = load_rules_from_yaml(f)
    assert rules[0].priority == 200
    assert rules[0].enabled is False
    assert rules[0].pattern_type == "regex"


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_rules_from_yaml(tmp_path / "nope.yaml")


def test_yaml_without_rules_key_raises(tmp_path: Path) -> None:
    f = _write(tmp_path, "outra_chave: []\n")
    with pytest.raises(ValueError, match="'rules'"):
        load_rules_from_yaml(f)


def test_rules_not_a_list_raises(tmp_path: Path) -> None:
    f = _write(tmp_path, "rules: 'a string instead of a list'\n")
    with pytest.raises(ValueError, match="must be a list"):
        load_rules_from_yaml(f)


def test_invalid_pattern_type_raises(tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        """
rules:
  - { pattern: "x", pattern_type: "fuzzy", category: "outros.diversos" }
""",
    )
    with pytest.raises(ValueError, match="Invalid rule"):
        load_rules_from_yaml(f)


def test_missing_required_field_raises(tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        """
rules:
  - { pattern: "x", pattern_type: "substring" }
""",
    )
    with pytest.raises(ValueError, match="Invalid rule"):
        load_rules_from_yaml(f)


def test_empty_rules_list_returns_empty(tmp_path: Path) -> None:
    f = _write(tmp_path, "rules: []\n")
    assert load_rules_from_yaml(f) == []
