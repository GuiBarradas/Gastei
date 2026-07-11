"""Specs for the pure insight aggregation functions — TDD."""

from __future__ import annotations

from datetime import date

import pytest

from gastei.domain.insights.aggregations import (
    monthly_summary,
    spending_by_category,
    top_merchants,
)
from gastei.schemas.transaction import Transaction

pytestmark = pytest.mark.unit


def _tx(
    *,
    tx_id: str = "t",
    amount: float = -50.0,
    category: str | None = "alimentacao.delivery",
    description: str = "iFood",
    merchant: str | None = None,
    when: date = date(2026, 5, 1),
) -> Transaction:
    return Transaction(
        id=tx_id,
        account_id="a1",
        date=when,
        amount=amount,
        description=description,
        merchant_name=merchant,
        category=category,
    )


# --------------------------------------------------------------------------------------
# spending_by_category
# --------------------------------------------------------------------------------------


def test_spending_by_category_aggregates_negative_amounts() -> None:
    txs = [
        _tx(tx_id="1", amount=-50.0, category="alimentacao.delivery"),
        _tx(tx_id="2", amount=-30.0, category="alimentacao.delivery"),
        _tx(tx_id="3", amount=-20.0, category="transporte.app"),
    ]
    result = spending_by_category(txs)

    by_cat = {r.category: r for r in result}
    assert by_cat["alimentacao.delivery"].amount == 80.0
    assert by_cat["alimentacao.delivery"].transaction_count == 2
    assert by_cat["transporte.app"].amount == 20.0


def test_spending_by_category_excludes_transfers_and_investments() -> None:
    txs = [
        _tx(tx_id="1", amount=-100.0, category="transferencia.entre_contas_proprias"),
        _tx(tx_id="2", amount=-200.0, category="investimento.aporte"),
        _tx(tx_id="3", amount=-50.0, category="alimentacao.delivery"),
    ]
    result = spending_by_category(txs)
    cats = {r.category for r in result}
    assert cats == {"alimentacao.delivery"}


def test_spending_by_category_excludes_income() -> None:
    """Receita (amount > 0) não conta como gasto, mesmo que categoria seja despesa."""
    txs = [
        _tx(tx_id="1", amount=5000.0, category="renda.salario"),
        _tx(tx_id="2", amount=-50.0, category="alimentacao.delivery"),
    ]
    result = spending_by_category(txs)
    assert len(result) == 1
    assert result[0].category == "alimentacao.delivery"


def test_spending_by_category_returns_top_n_with_others_bucket() -> None:
    txs = [_tx(tx_id=str(i), amount=-(i * 10), category=f"cat.{i}") for i in range(1, 11)]
    result = spending_by_category(txs, top_n=3)

    # Top 3: cat.10 (100), cat.9 (90), cat.8 (80) + "outros" agregando o resto
    assert len(result) == 4
    assert [r.category for r in result[:3]] == ["cat.10", "cat.9", "cat.8"]
    assert result[3].category == "outros"
    assert result[3].amount == sum(i * 10 for i in range(1, 8))  # 1+2+...+7 = 28 → *10 = 280


def test_spending_by_category_groups_uncategorized() -> None:
    txs = [
        _tx(tx_id="1", amount=-10.0, category=None),
        _tx(tx_id="2", amount=-20.0, category=None),
        _tx(tx_id="3", amount=-30.0, category="alimentacao.delivery"),
    ]
    result = spending_by_category(txs)
    by_cat = {r.category: r for r in result}
    assert by_cat["sem_categoria"].amount == 30.0
    assert by_cat["sem_categoria"].transaction_count == 2


def test_spending_by_category_sorted_desc() -> None:
    txs = [
        _tx(tx_id="1", amount=-10.0, category="a"),
        _tx(tx_id="2", amount=-100.0, category="b"),
        _tx(tx_id="3", amount=-50.0, category="c"),
    ]
    result = spending_by_category(txs)
    assert [r.category for r in result] == ["b", "c", "a"]


def test_spending_by_category_empty_list() -> None:
    assert spending_by_category([]) == []


# --------------------------------------------------------------------------------------
# monthly_summary
# --------------------------------------------------------------------------------------


def test_monthly_summary_separates_income_and_expense() -> None:
    txs = [
        _tx(tx_id="1", amount=5000.0, category="renda.salario", when=date(2026, 4, 1)),
        _tx(tx_id="2", amount=-50.0, category="alimentacao.delivery", when=date(2026, 4, 5)),
        _tx(tx_id="3", amount=-100.0, category="transporte.app", when=date(2026, 4, 10)),
    ]
    result = monthly_summary(txs)
    assert len(result) == 1
    assert result[0].year == 2026
    assert result[0].month == 4
    assert result[0].income == 5000.0
    assert result[0].expense == 150.0
    assert result[0].net == 4850.0


def test_monthly_summary_excludes_transfers_and_investments() -> None:
    txs = [
        _tx(tx_id="1", amount=-1000.0, category="transferencia.entre_contas_proprias"),
        _tx(tx_id="2", amount=2000.0, category="investimento.resgate"),
        _tx(tx_id="3", amount=-50.0, category="alimentacao.delivery"),
    ]
    result = monthly_summary(txs)
    assert result[0].income == 0.0
    assert result[0].expense == 50.0


def test_monthly_summary_groups_by_year_month() -> None:
    txs = [
        _tx(tx_id="1", amount=-100.0, category="alimentacao.delivery", when=date(2026, 3, 15)),
        _tx(tx_id="2", amount=-200.0, category="alimentacao.delivery", when=date(2026, 4, 1)),
        _tx(tx_id="3", amount=-50.0, category="alimentacao.delivery", when=date(2026, 4, 28)),
    ]
    result = monthly_summary(txs)
    assert len(result) == 2
    by_month = {(r.year, r.month): r for r in result}
    assert by_month[(2026, 3)].expense == 100.0
    assert by_month[(2026, 4)].expense == 250.0


def test_monthly_summary_sorted_chronologically() -> None:
    txs = [
        _tx(tx_id="1", amount=-10.0, category="alimentacao.delivery", when=date(2026, 5, 1)),
        _tx(tx_id="2", amount=-10.0, category="alimentacao.delivery", when=date(2026, 3, 1)),
        _tx(tx_id="3", amount=-10.0, category="alimentacao.delivery", when=date(2026, 4, 1)),
    ]
    result = monthly_summary(txs)
    assert [(r.year, r.month) for r in result] == [(2026, 3), (2026, 4), (2026, 5)]


# --------------------------------------------------------------------------------------
# top_merchants
# --------------------------------------------------------------------------------------


def test_top_merchants_uses_merchant_name_when_present() -> None:
    txs = [
        _tx(tx_id="1", amount=-50.0, merchant="iFood", description="X"),
        _tx(tx_id="2", amount=-30.0, merchant="iFood", description="Y"),
        _tx(tx_id="3", amount=-20.0, merchant="Uber", description="Z"),
    ]
    result = top_merchants(txs, limit=10)
    by_m = {r.merchant: r for r in result}
    assert by_m["iFood"].amount == 80.0
    assert by_m["iFood"].transaction_count == 2


def test_top_merchants_falls_back_to_description() -> None:
    txs = [
        _tx(tx_id="1", amount=-50.0, merchant=None, description="IFOOD *X"),
    ]
    result = top_merchants(txs, limit=10)
    assert result[0].merchant == "IFOOD *X"


def test_top_merchants_only_expenses() -> None:
    txs = [
        _tx(tx_id="1", amount=5000.0, merchant="Empresa", category="renda.salario"),
        _tx(tx_id="2", amount=-50.0, merchant="iFood"),
    ]
    result = top_merchants(txs, limit=10)
    assert {r.merchant for r in result} == {"iFood"}


def test_top_merchants_truncates_at_limit() -> None:
    txs = [_tx(tx_id=str(i), amount=-(i * 10), merchant=f"m{i}") for i in range(1, 11)]
    result = top_merchants(txs, limit=3)
    assert len(result) == 3
    assert [r.merchant for r in result] == ["m10", "m9", "m8"]
