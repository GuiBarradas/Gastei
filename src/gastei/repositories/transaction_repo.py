"""SQLAlchemyTransactionRepository — adapter implementing the ``TransactionRepository`` port.

Method signatures are async (matching the port — future-proofed for a move
to Postgres + asyncpg), but the body uses a synchronous ``Session``. Local
SQLite is sub-millisecond, so the overhead of ``aiosqlite`` is not worth it
for a single-user MVP.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from gastei.models.transaction import Transaction as TransactionORM
from gastei.schemas.transaction import Transaction


class SQLAlchemyTransactionRepository:
    """Implements ``gastei.domain.ports.TransactionRepository``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def upsert_many(self, txs: list[Transaction]) -> tuple[int, int]:
        if not txs:
            return 0, 0

        ids = [tx.id for tx in txs]
        existing_ids = set(
            self._session.scalars(select(TransactionORM.id).where(TransactionORM.id.in_(ids))).all()
        )

        inserted = 0
        updated = 0
        for tx in txs:
            if tx.id in existing_ids:
                self._session.merge(self._to_orm(tx))
                updated += 1
            else:
                self._session.add(self._to_orm(tx))
                inserted += 1

        self._session.commit()
        return inserted, updated

    async def get(self, tx_id: str) -> Transaction | None:
        row = self._session.get(TransactionORM, tx_id)
        return Transaction.model_validate(row) if row is not None else None

    async def list_by_account(
        self,
        account_id: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[Transaction]:
        stmt = (
            select(TransactionORM)
            .where(TransactionORM.account_id == account_id)
            .order_by(TransactionORM.date.desc())
        )
        if start is not None:
            stmt = stmt.where(TransactionORM.date >= start)
        if end is not None:
            stmt = stmt.where(TransactionORM.date <= end)

        rows = self._session.scalars(stmt).all()
        return [Transaction.model_validate(row) for row in rows]

    async def list_uncategorized(self, limit: int = 100) -> list[Transaction]:
        stmt = select(TransactionORM).where(TransactionORM.category.is_(None)).limit(limit)
        rows = self._session.scalars(stmt).all()
        return [Transaction.model_validate(row) for row in rows]

    async def update_category(
        self,
        tx_id: str,
        category: str,
        source: str,
        confidence: float | None = None,
    ) -> None:
        orm_tx = self._session.get(TransactionORM, tx_id)
        if orm_tx is None:
            raise KeyError(tx_id)
        orm_tx.category = category
        orm_tx.category_source = source
        orm_tx.category_confidence = confidence
        self._session.commit()

    @staticmethod
    def _to_orm(tx: Transaction) -> TransactionORM:
        return TransactionORM(
            id=tx.id,
            account_id=tx.account_id,
            date=tx.date,
            amount=tx.amount,
            description=tx.description,
            description_raw=tx.description_raw,
            merchant_name=tx.merchant_name,
            category=tx.category,
            category_source=tx.category_source,
            category_confidence=tx.category_confidence,
            pluggy_category=tx.pluggy_category,
            payment_method=tx.payment_method,
        )
