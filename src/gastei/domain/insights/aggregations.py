"""Pure aggregation functions over transactions.

No I/O. These functions take ``list[Transaction]`` and return DTOs from
``schemas.insights``. They centralize the rule of "what counts as income
vs. expense" — transfer and investment categories are neutral and do not
flow through revenue or spending totals.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from gastei.schemas.insights import (
    CategorySpending,
    MerchantSpending,
    MonthlySummary,
)
from gastei.schemas.transaction import Transaction

# Category prefixes that do NOT count as income or expense.
NEUTRAL_CATEGORY_PREFIXES = ("transferencia.", "investimento.")
UNCATEGORIZED_LABEL = "sem_categoria"
OTHERS_LABEL = "outros"


def _is_neutral(category: str | None) -> bool:
    if category is None:
        return False
    return category.startswith(NEUTRAL_CATEGORY_PREFIXES)


def _is_expense(tx: Transaction) -> bool:
    return tx.amount < 0 and not _is_neutral(tx.category)


def _is_income(tx: Transaction) -> bool:
    return tx.amount > 0 and not _is_neutral(tx.category)


def spending_by_category(
    txs: Iterable[Transaction], top_n: int | None = None
) -> list[CategorySpending]:
    """Aggregate absolute expense amounts by category.

    - Excludes transfers and investments (neutral by design).
    - Excludes income (amount > 0).
    - ``category=None`` is grouped into the ``"sem_categoria"`` bucket.
    - When ``top_n`` is given, returns the top N plus an ``"outros"``
      bucket aggregating the rest.
    - Sorted by amount descending.
    """
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)

    for tx in txs:
        if not _is_expense(tx):
            continue
        key = tx.category or UNCATEGORIZED_LABEL
        totals[key] += abs(tx.amount)
        counts[key] += 1

    rows = [
        CategorySpending(category=cat, amount=amt, transaction_count=counts[cat])
        for cat, amt in totals.items()
    ]
    rows.sort(key=lambda r: r.amount, reverse=True)

    if top_n is not None and len(rows) > top_n:
        head = rows[:top_n]
        tail = rows[top_n:]
        others = CategorySpending(
            category=OTHERS_LABEL,
            amount=sum(r.amount for r in tail),
            transaction_count=sum(r.transaction_count for r in tail),
        )
        return [*head, others]

    return rows


def monthly_summary(txs: Iterable[Transaction]) -> list[MonthlySummary]:
    """Aggregate by (year, month). ``income`` and ``expense`` are positive totals."""
    income_by_month: dict[tuple[int, int], float] = defaultdict(float)
    expense_by_month: dict[tuple[int, int], float] = defaultdict(float)

    for tx in txs:
        key = (tx.date.year, tx.date.month)
        if _is_income(tx):
            income_by_month[key] += tx.amount
        elif _is_expense(tx):
            expense_by_month[key] += abs(tx.amount)

    months = sorted(set(income_by_month) | set(expense_by_month))
    return [
        MonthlySummary(
            year=year,
            month=month,
            income=income_by_month[(year, month)],
            expense=expense_by_month[(year, month)],
            net=income_by_month[(year, month)] - expense_by_month[(year, month)],
        )
        for year, month in months
    ]


def top_merchants(txs: Iterable[Transaction], limit: int = 10) -> list[MerchantSpending]:
    """Top N merchants by spend. Uses ``merchant_name`` and falls back to ``description``."""
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)

    for tx in txs:
        if not _is_expense(tx):
            continue
        key = tx.merchant_name or tx.description
        totals[key] += abs(tx.amount)
        counts[key] += 1

    rows = [
        MerchantSpending(merchant=m, amount=amt, transaction_count=counts[m])
        for m, amt in totals.items()
    ]
    rows.sort(key=lambda r: r.amount, reverse=True)
    return rows[:limit]
