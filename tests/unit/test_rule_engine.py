"""RuleEngine specs — TDD (ARCHITECTURE.md §7.2).

Coverage:

- substring matching, case-insensitive
- regex matching, IGNORECASE flag applied at compile time
- merchant_exact matching (compared against ``tx.merchant_name``)
- ordering by ``priority`` descending (highest wins)
- ties in ``priority`` resolved by insertion order (stable)
- ``enabled=False`` rules are skipped
- ``match()`` returns ``None`` when nothing fits
- an invalid regex fails fast at construction time
- regex patterns are pre-compiled (not recompiled per ``match()``)
"""

from __future__ import annotations

from datetime import date

import pytest

from gastei.domain.categorizer.rule_engine import RuleEngine
from gastei.schemas.rule import Rule
from gastei.schemas.transaction import Transaction

pytestmark = pytest.mark.unit


def _tx(
    description: str = "IFOOD *RESTAURANTE",
    merchant: str | None = None,
    tx_id: str = "t1",
) -> Transaction:
    return Transaction(
        id=tx_id,
        account_id="a1",
        date=date(2026, 5, 1),
        amount=-50.0,
        description=description,
        merchant_name=merchant,
    )


# --------------------------------------------------------------------------------------
# Substring matching
# --------------------------------------------------------------------------------------


def test_substring_match_case_insensitive() -> None:
    engine = RuleEngine(
        [
            Rule(pattern="ifood", pattern_type="substring", category="alimentacao.delivery"),
        ]
    )
    match = engine.match(_tx("IFOOD *RESTAURANTE"))
    assert match is not None
    assert match.category == "alimentacao.delivery"


def test_substring_no_match_returns_none() -> None:
    engine = RuleEngine(
        [
            Rule(pattern="netflix", pattern_type="substring", category="lazer.streaming"),
        ]
    )
    assert engine.match(_tx("Pagamento iFood")) is None


def test_empty_rules_returns_none() -> None:
    assert RuleEngine([]).match(_tx()) is None


# --------------------------------------------------------------------------------------
# Regex matching
# --------------------------------------------------------------------------------------


def test_regex_match_case_insensitive() -> None:
    engine = RuleEngine(
        [
            Rule(
                pattern=r"^uber\b",
                pattern_type="regex",
                category="transporte.app",
            ),
        ]
    )
    assert engine.match(_tx("UBER *TRIP")).category == "transporte.app"
    assert engine.match(_tx("uber eats")).category == "transporte.app"
    assert engine.match(_tx("super bowl")) is None


def test_invalid_regex_raises_at_construction() -> None:
    with pytest.raises((ValueError, Exception)):
        RuleEngine(
            [
                Rule(pattern="[unclosed", pattern_type="regex", category="outros.diversos"),
            ]
        )


# --------------------------------------------------------------------------------------
# Merchant_exact matching
# --------------------------------------------------------------------------------------


def test_merchant_exact_matches_when_equal() -> None:
    engine = RuleEngine(
        [
            Rule(pattern="Netflix", pattern_type="merchant_exact", category="lazer.streaming"),
        ]
    )
    assert engine.match(_tx("qualquer descricao", merchant="netflix")).category == "lazer.streaming"


def test_merchant_exact_does_not_match_substring() -> None:
    engine = RuleEngine(
        [
            Rule(pattern="Netflix", pattern_type="merchant_exact", category="lazer.streaming"),
        ]
    )
    assert engine.match(_tx("x", merchant="netflix brasil ltda")) is None


def test_merchant_exact_skips_when_merchant_is_none() -> None:
    engine = RuleEngine(
        [
            Rule(pattern="Netflix", pattern_type="merchant_exact", category="lazer.streaming"),
        ]
    )
    assert engine.match(_tx("netflix", merchant=None)) is None


# --------------------------------------------------------------------------------------
# Prioridade
# --------------------------------------------------------------------------------------


def test_higher_priority_wins() -> None:
    engine = RuleEngine(
        [
            Rule(
                pattern="pix",
                pattern_type="substring",
                category="transferencia.pix_terceiros",
                priority=10,
            ),
            Rule(pattern="pix", pattern_type="substring", category="renda.salario", priority=200),
        ]
    )
    assert engine.match(_tx("PIX recebido")).category == "renda.salario"


def test_priority_tie_resolves_by_list_order() -> None:
    engine = RuleEngine(
        [
            Rule(
                pattern="ifood",
                pattern_type="substring",
                category="alimentacao.delivery",
                priority=100,
            ),
            Rule(
                pattern="ifood",
                pattern_type="substring",
                category="alimentacao.restaurante",
                priority=100,
            ),
        ]
    )
    assert engine.match(_tx("ifood pedido")).category == "alimentacao.delivery"


def test_disabled_rules_are_skipped() -> None:
    engine = RuleEngine(
        [
            Rule(
                pattern="ifood",
                pattern_type="substring",
                category="alimentacao.delivery",
                enabled=False,
                priority=200,
            ),
            Rule(
                pattern="ifood",
                pattern_type="substring",
                category="alimentacao.restaurante",
                priority=100,
            ),
        ]
    )
    assert engine.match(_tx("ifood")).category == "alimentacao.restaurante"


# --------------------------------------------------------------------------------------
# Performance / pré-compilação
# --------------------------------------------------------------------------------------


def test_regex_is_precompiled_once_at_init(monkeypatch: pytest.MonkeyPatch) -> None:
    """``match()`` must not call ``re.compile`` — RuleEngine pre-compiles in ``__init__``."""
    import re

    compile_calls = {"n": 0}
    real_compile = re.compile

    def counting_compile(*args, **kwargs):
        compile_calls["n"] += 1
        return real_compile(*args, **kwargs)

    engine = RuleEngine(
        [
            Rule(pattern=r"\bifood\b", pattern_type="regex", category="alimentacao.delivery"),
        ]
    )
    baseline = compile_calls["n"]

    monkeypatch.setattr(re, "compile", counting_compile)
    for _ in range(10):
        engine.match(_tx("ifood pedido"))

    after_match = compile_calls["n"] - baseline
    assert after_match == 0, f"re.compile was called {after_match}x inside match() — should be 0"
