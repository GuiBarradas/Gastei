"""``GET /insights/*`` — dashboard aggregations."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from gastei.api.deps import get_db_session, get_transaction_repo
from gastei.api.routers.transactions import resolve_account_ids
from gastei.domain.insights.aggregations import (
    monthly_summary as _monthly_summary,
)
from gastei.domain.insights.aggregations import (
    spending_by_category as _spending_by_category,
)
from gastei.domain.insights.aggregations import (
    top_merchants as _top_merchants,
)
from gastei.domain.ports import TransactionRepository
from gastei.models.account import Account as AccountORM
from gastei.models.item import Item as ItemORM
from gastei.schemas.insights import (
    BankBalance,
    CategorySpending,
    MerchantSpending,
    MonthlySummary,
)
from gastei.schemas.transaction import Transaction

router = APIRouter(prefix="/insights", tags=["insights"])


async def _gather_transactions(
    repo: TransactionRepository,
    session: Session,
    account_id: str | None,
    item_id: str | None,
    start: date | None,
    end: date | None,
) -> list[Transaction]:
    """Aggregate transactions from one or many accounts based on the filter (bank / account / all)."""
    account_ids = resolve_account_ids(session, account_id=account_id, item_id=item_id)
    all_txs: list[Transaction] = []
    for aid in account_ids:
        all_txs.extend(await repo.list_by_account(aid, start=start, end=end))
    return all_txs


@router.get("/spending-by-category", response_model=list[CategorySpending])
async def spending_by_category(
    account_id: str | None = Query(None),
    item_id: str | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
    top_n: int = Query(8, ge=1, le=50),
    session: Session = Depends(get_db_session),
    repo: TransactionRepository = Depends(get_transaction_repo),
) -> list[CategorySpending]:
    txs = await _gather_transactions(repo, session, account_id, item_id, start, end)
    return _spending_by_category(txs, top_n=top_n)


@router.get("/monthly-summary", response_model=list[MonthlySummary])
async def monthly_summary(
    account_id: str | None = Query(None),
    item_id: str | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
    session: Session = Depends(get_db_session),
    repo: TransactionRepository = Depends(get_transaction_repo),
) -> list[MonthlySummary]:
    txs = await _gather_transactions(repo, session, account_id, item_id, start, end)
    return _monthly_summary(txs)


@router.get("/top-merchants", response_model=list[MerchantSpending])
async def top_merchants(
    account_id: str | None = Query(None),
    item_id: str | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_db_session),
    repo: TransactionRepository = Depends(get_transaction_repo),
) -> list[MerchantSpending]:
    txs = await _gather_transactions(repo, session, account_id, item_id, start, end)
    return _top_merchants(txs, limit=limit)


@router.get("/balances-by-bank", response_model=list[BankBalance])
def balances_by_bank(
    session: Session = Depends(get_db_session),
) -> list[BankBalance]:
    """Aggregated balance per bank (one row per institution)."""
    rows = session.execute(
        select(
            ItemORM.id,
            ItemORM.institution_name,
            AccountORM.balance,
        ).join(AccountORM, AccountORM.item_id == ItemORM.id)
    ).all()

    by_bank: dict[str, dict] = {}
    for item_id, name, balance in rows:
        key = item_id
        if key not in by_bank:
            by_bank[key] = {
                "institution_id": item_id,
                "bank_name": name,
                "account_count": 0,
                "total_balance": 0.0,
            }
        by_bank[key]["account_count"] += 1
        by_bank[key]["total_balance"] += float(balance or 0)

    return [
        BankBalance(**v)
        for v in sorted(by_bank.values(), key=lambda b: b["total_balance"], reverse=True)
    ]
