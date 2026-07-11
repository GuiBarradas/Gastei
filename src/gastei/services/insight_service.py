"""InsightsService — orchestrates the repository and the pure aggregation functions.

Thin service layer: fetches data through the repository, calls the pure
functions in ``gastei.domain.insights.aggregations``, returns DTOs.
"""

from __future__ import annotations

from datetime import date

from gastei.domain.insights.aggregations import (
    monthly_summary,
    spending_by_category,
    top_merchants,
)
from gastei.domain.ports import TransactionRepository
from gastei.schemas.insights import (
    CategorySpending,
    MerchantSpending,
    MonthlySummary,
)


class InsightsService:
    def __init__(self, repo: TransactionRepository) -> None:
        self._repo = repo

    async def spending_by_category(
        self,
        account_id: str,
        start: date | None = None,
        end: date | None = None,
        top_n: int | None = 8,
    ) -> list[CategorySpending]:
        txs = await self._repo.list_by_account(account_id, start=start, end=end)
        return spending_by_category(txs, top_n=top_n)

    async def monthly_summary(
        self,
        account_id: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[MonthlySummary]:
        txs = await self._repo.list_by_account(account_id, start=start, end=end)
        return monthly_summary(txs)

    async def top_merchants(
        self,
        account_id: str,
        start: date | None = None,
        end: date | None = None,
        limit: int = 10,
    ) -> list[MerchantSpending]:
        txs = await self._repo.list_by_account(account_id, start=start, end=end)
        return top_merchants(txs, limit=limit)
