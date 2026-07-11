"""Tools exposed to the InsightAgent (ARCHITECTURE.md §7.3).

Each ``AgentTool`` is an async callable plus a JSON Schema. The agent dispatches
by ``name`` when the LLM emits a ``tool_use`` block. Tools are constructed via
a factory with their dependencies injected.

``account_id`` is optional on the insight tools: omitted, they consolidate
across every account (the LLM has no way to know internal ids up front —
``list_accounts`` exists for drill-downs).

Tool output strings are rendered in Portuguese because they are read by an
LLM that talks to a Brazilian user. The tool *contracts* (names, parameter
docs) stay in English because they live in code.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from gastei.domain.insights import aggregations as agg
from gastei.domain.ports import TransactionRepository
from gastei.schemas.transaction import Transaction

ToolCallable = Callable[..., Awaitable[str]]
AccountsProvider = Callable[[], list[dict[str, Any]]]


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


def _fmt_brl(v: float) -> str:
    # No thousands separator: "5,000.00" reads as 5.00 to a pt-BR model.
    return f"R$ {v:.2f}"


# ----------------------------------------------------------------------------
# Factory
# ----------------------------------------------------------------------------


def make_default_tools(
    *,
    repo: TransactionRepository,
    list_accounts: AccountsProvider | None = None,
) -> list[AgentTool]:
    """Five tools that cover the typical conversational queries.

    ``list_accounts`` supplies ``{"id", "name", "bank", "balance"}`` dicts; when
    absent, the consolidated (no ``account_id``) path is unavailable and the
    ``list_accounts`` tool is not registered.
    """

    async def _txs(
        account_id: str | None,
        start: date | None,
        end: date | None,
    ) -> list[Transaction]:
        if account_id:
            return await repo.list_by_account(account_id, start=start, end=end)
        if list_accounts is None:
            raise ValueError("account_id is required — no accounts provider wired in")
        out: list[Transaction] = []
        for acc in list_accounts():
            out.extend(await repo.list_by_account(acc["id"], start=start, end=end))
        return out

    async def _spending_by_category(
        account_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        top_n: int = 8,
    ) -> str:
        txs = await _txs(account_id, _parse_date(start_date), _parse_date(end_date))
        rows = agg.spending_by_category(txs, top_n=top_n)
        if not rows:
            return "Nenhum gasto registrado no período."
        lines = [f"- {r.category}: {_fmt_brl(r.amount)} ({r.transaction_count} tx)" for r in rows]
        return "Gastos por categoria:\n" + "\n".join(lines)

    async def _top_merchants(
        account_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
    ) -> str:
        txs = await _txs(account_id, _parse_date(start_date), _parse_date(end_date))
        rows = agg.top_merchants(txs, limit=limit)
        if not rows:
            return "Nenhum estabelecimento no período."
        lines = [f"- {r.merchant}: {_fmt_brl(r.amount)} ({r.transaction_count} tx)" for r in rows]
        return "Top estabelecimentos:\n" + "\n".join(lines)

    async def _monthly_summary(
        account_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        txs = await _txs(account_id, _parse_date(start_date), _parse_date(end_date))
        rows = agg.monthly_summary(txs)
        if not rows:
            return "Sem dados mensais no período."
        lines = [
            f"- {r.year}-{r.month:02d}: receitas {_fmt_brl(r.income)}, "
            f"despesas {_fmt_brl(r.expense)}, saldo {_fmt_brl(r.net)}"
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

    async def _list_accounts() -> str:
        assert list_accounts is not None
        accounts = list_accounts()
        if not accounts:
            return "Nenhuma conta cadastrada."
        lines = [
            f"- {a.get('bank', '?')} · {a['name']} — id={a['id']} — saldo {_fmt_brl(a['balance'])}"
            for a in accounts
        ]
        return "Contas disponíveis:\n" + "\n".join(lines)

    period_props = {
        "account_id": {
            "type": "string",
            "description": (
                "Internal account id. Optional — omit to consolidate across all "
                "accounts. Use list_accounts to discover ids for drill-downs."
            ),
        },
        "start_date": {
            "type": "string",
            "description": "ISO YYYY-MM-DD. Optional.",
        },
        "end_date": {
            "type": "string",
            "description": "ISO YYYY-MM-DD. Optional.",
        },
    }

    tools = [
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
                "required": [],
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
                "required": [],
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
                "required": [],
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

    if list_accounts is not None:
        tools.append(
            AgentTool(
                name="list_accounts",
                description=(
                    "List the user's bank accounts (bank, name, internal id, balance). "
                    "Call this before drilling down into a specific account."
                ),
                input_schema={"type": "object", "properties": {}, "required": []},
                fn=_list_accounts,
            )
        )

    return tools
