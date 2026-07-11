"""Tools exposed to the InsightAgent (ARCHITECTURE.md §7.3).

Each ``AgentTool`` is an async callable plus a JSON Schema. The agent dispatches
by ``name`` when the LLM emits a ``tool_use`` block. Tools are constructed via
a factory with their dependencies (services, repositories) injected.

Tool output strings are rendered in Portuguese because they are read by an
LLM that talks to a Brazilian user. The tool *contracts* (names, parameter
docs) stay in English because they live in code.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from gastei.domain.ports import TransactionRepository
from gastei.services.insight_service import InsightsService

ToolCallable = Callable[..., Awaitable[str]]


@dataclass(frozen=True)
class AgentTool:
    """Tool exposed to the LLM. Serialized via ``schema`` in Anthropic's tool-use format."""

    name: str
    description: str
    input_schema: dict[str, Any]
    fn: ToolCallable

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        return await self.fn(**arguments)


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


# ----------------------------------------------------------------------------
# Factory
# ----------------------------------------------------------------------------


def make_default_tools(
    *, insights: InsightsService, repo: TransactionRepository
) -> list[AgentTool]:
    """Four tools that cover ~80% of typical conversational queries."""

    async def _spending_by_category(
        account_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        top_n: int = 8,
    ) -> str:
        rows = await insights.spending_by_category(
            account_id=account_id,
            start=_parse_date(start_date),
            end=_parse_date(end_date),
            top_n=top_n,
        )
        if not rows:
            return "Nenhum gasto registrado no período."
        lines = [f"- {r.category}: R$ {r.amount:.2f} ({r.transaction_count} tx)" for r in rows]
        return "Gastos por categoria:\n" + "\n".join(lines)

    async def _top_merchants(
        account_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
    ) -> str:
        rows = await insights.top_merchants(
            account_id=account_id,
            start=_parse_date(start_date),
            end=_parse_date(end_date),
            limit=limit,
        )
        if not rows:
            return "Nenhum estabelecimento no período."
        lines = [f"- {r.merchant}: R$ {r.amount:.2f} ({r.transaction_count} tx)" for r in rows]
        return "Top estabelecimentos:\n" + "\n".join(lines)

    async def _monthly_summary(
        account_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        rows = await insights.monthly_summary(
            account_id=account_id,
            start=_parse_date(start_date),
            end=_parse_date(end_date),
        )
        if not rows:
            return "Sem dados mensais no período."
        lines = [
            f"- {r.year}-{r.month:02d}: receitas R$ {r.income:.2f}, "
            f"despesas R$ {r.expense:.2f}, saldo R$ {r.net:.2f}"
            for r in rows
        ]
        return "Resumo mensal:\n" + "\n".join(lines)

    async def _list_uncategorized(limit: int = 20) -> str:
        rows = await repo.list_uncategorized(limit=limit)
        if not rows:
            return "Nenhuma transação sem categoria."
        lines = [
            f"- id={tx.id} | {tx.date.isoformat()} | R$ {tx.amount:.2f} | {tx.description!r}"
            for tx in rows
        ]
        return "Transações sem categoria:\n" + "\n".join(lines)

    period_props = {
        "account_id": {"type": "string", "description": "Internal Account id."},
        "start_date": {
            "type": "string",
            "description": "ISO YYYY-MM-DD. Optional.",
        },
        "end_date": {
            "type": "string",
            "description": "ISO YYYY-MM-DD. Optional.",
        },
    }

    return [
        AgentTool(
            name="get_spending_by_category",
            description=(
                "Sum expenses (amount < 0) by category over a date range, "
                "excluding transfers and investments. Returns formatted text."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    **period_props,
                    "top_n": {
                        "type": "integer",
                        "description": "Top N + an 'others' bucket. Default 8.",
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": ["account_id"],
            },
            fn=_spending_by_category,
        ),
        AgentTool(
            name="get_top_merchants",
            description="Top merchants by spend (expenses, absolute value).",
            input_schema={
                "type": "object",
                "properties": {
                    **period_props,
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ["account_id"],
            },
            fn=_top_merchants,
        ),
        AgentTool(
            name="get_monthly_summary",
            description=(
                "Income, expense and net balance aggregated per (year, month). "
                "Excludes transfers and investments."
            ),
            input_schema={
                "type": "object",
                "properties": period_props,
                "required": ["account_id"],
            },
            fn=_monthly_summary,
        ),
        AgentTool(
            name="list_uncategorized",
            description="List transactions without a category — useful for manual review.",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                "required": [],
            },
            fn=_list_uncategorized,
        ),
    ]
