"""Tests for the default InsightAgent tools.

Each tool is exercised against ``FakeTransactionRepository`` plus the real
``InsightsService`` (which is a thin layer over the pure aggregations
already covered by ``test_aggregations``).
"""

from __future__ import annotations

from datetime import date

import pytest

from gastei.agents.tools import make_default_tools
from gastei.schemas.transaction import Transaction
from gastei.services.insight_service import InsightsService
from tests.fakes import FakeTransactionRepository

pytestmark = pytest.mark.unit


def _seeded_repo() -> FakeTransactionRepository:
    return FakeTransactionRepository(
        seed=[
            Transaction(
                id="t1",
                account_id="a",
                date=date(2026, 4, 5),
                amount=-50.0,
                description="iFood",
                category="alimentacao.delivery",
                merchant_name="iFood",
            ),
            Transaction(
                id="t2",
                account_id="a",
                date=date(2026, 4, 10),
                amount=-30.0,
                description="Uber",
                category="transporte.app",
                merchant_name="Uber",
            ),
            Transaction(
                id="t3",
                account_id="a",
                date=date(2026, 4, 20),
                amount=5000.0,
                description="Salario",
                category="renda.salario",
            ),
            Transaction(
                id="t4",
                account_id="a",
                date=date(2026, 4, 25),
                amount=-100.0,
                description="Misterio",
                category=None,
            ),
        ]
    )


def _tool_by_name(tools, name):
    return next(t for t in tools if t.name == name)


# ---------------- get_spending_by_category ----------------


async def test_spending_by_category_returns_formatted_text() -> None:
    repo = _seeded_repo()
    tools = make_default_tools(insights=InsightsService(repo), repo=repo)
    tool = _tool_by_name(tools, "get_spending_by_category")

    out = await tool.execute({"account_id": "a"})

    assert "alimentacao.delivery" in out
    assert "50.00" in out
    assert "transporte.app" in out


async def test_spending_by_category_filters_by_date() -> None:
    repo = _seeded_repo()
    tools = make_default_tools(insights=InsightsService(repo), repo=repo)
    tool = _tool_by_name(tools, "get_spending_by_category")

    out = await tool.execute(
        {
            "account_id": "a",
            "start_date": "2026-04-15",
            "end_date": "2026-04-30",
        }
    )
    # Só t4 (sem categoria) cai no range — apparece como sem_categoria
    assert "alimentacao.delivery" not in out
    assert "sem_categoria" in out


async def test_spending_by_category_empty_period_returns_message() -> None:
    repo = _seeded_repo()
    tools = make_default_tools(insights=InsightsService(repo), repo=repo)
    tool = _tool_by_name(tools, "get_spending_by_category")

    out = await tool.execute(
        {
            "account_id": "a",
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
        }
    )
    assert "Nenhum gasto" in out


# ---------------- get_top_merchants ----------------


async def test_top_merchants_returns_sorted_by_spend() -> None:
    repo = _seeded_repo()
    tools = make_default_tools(insights=InsightsService(repo), repo=repo)
    tool = _tool_by_name(tools, "get_top_merchants")

    out = await tool.execute({"account_id": "a", "limit": 5})
    assert "iFood" in out
    assert "Uber" in out
    # Salario é receita — não vira merchant
    assert "Salario" not in out


# ---------------- get_monthly_summary ----------------


async def test_monthly_summary_separates_income_and_expense() -> None:
    repo = _seeded_repo()
    tools = make_default_tools(insights=InsightsService(repo), repo=repo)
    tool = _tool_by_name(tools, "get_monthly_summary")

    out = await tool.execute({"account_id": "a"})
    assert "2026-04" in out
    assert "5000.00" in out  # receita
    assert "180.00" in out  # despesa: 50 + 30 + 100


# ---------------- list_uncategorized ----------------


async def test_list_uncategorized_returns_only_null_category() -> None:
    repo = _seeded_repo()
    tools = make_default_tools(insights=InsightsService(repo), repo=repo)
    tool = _tool_by_name(tools, "list_uncategorized")

    out = await tool.execute({})
    assert "t4" in out
    assert "Misterio" in out
    assert "iFood" not in out


async def test_list_uncategorized_respects_limit() -> None:
    seed = [
        Transaction(
            id=f"t{i}",
            account_id="a",
            date=date(2026, 4, i),
            amount=-1.0,
            description=f"d{i}",
            category=None,
        )
        for i in range(1, 11)
    ]
    repo = FakeTransactionRepository(seed=seed)
    tools = make_default_tools(insights=InsightsService(repo), repo=repo)
    tool = _tool_by_name(tools, "list_uncategorized")

    out = await tool.execute({"limit": 3})
    # 3 ids aparecem, dos 10 sem categoria
    assert sum(out.count(f"t{i}") for i in range(1, 11)) == 3


# ---------------- Schemas das tools ----------------


def test_all_tools_have_valid_schemas() -> None:
    repo = FakeTransactionRepository()
    tools = make_default_tools(insights=InsightsService(repo), repo=repo)
    for t in tools:
        s = t.schema
        assert s["name"] == t.name
        assert s["description"]
        assert s["input_schema"]["type"] == "object"
        assert "properties" in s["input_schema"]
