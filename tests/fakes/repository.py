"""FakeTransactionRepository — stores transactions in an in-memory dict."""

from __future__ import annotations

from datetime import date

from gastei.schemas.transaction import Transaction


class FakeTransactionRepository:
    """Implements ``gastei.domain.ports.TransactionRepository`` in memory.

    Public inspection attributes for tests:

    - ``_store``: ``dict[id, Transaction]``
    - ``update_category_calls``: list of ``(tx_id, category, source, confidence)`` tuples
    """

    def __init__(self, seed: list[Transaction] | None = None) -> None:
        self._store: dict[str, Transaction] = {}
        self.update_category_calls: list[tuple[str, str, str, float | None]] = []
        if seed:
            for tx in seed:
                self._store[tx.id] = tx

    async def upsert_many(self, txs: list[Transaction]) -> tuple[int, int]:
        inserted = 0
        updated = 0
        for tx in txs:
            if tx.id in self._store:
                updated += 1
            else:
                inserted += 1
            self._store[tx.id] = tx
        return inserted, updated

    async def list_by_account(
        self,
        account_id: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[Transaction]:
        result = [tx for tx in self._store.values() if tx.account_id == account_id]
        if start is not None:
            result = [tx for tx in result if tx.date >= start]
        if end is not None:
            result = [tx for tx in result if tx.date <= end]
        return sorted(result, key=lambda t: t.date, reverse=True)

    async def list_uncategorized(self, limit: int = 100) -> list[Transaction]:
        result = [tx for tx in self._store.values() if tx.category is None]
        return result[:limit]

    async def update_category(
        self,
        tx_id: str,
        category: str,
        source: str,
        confidence: float | None = None,
    ) -> None:
        self.update_category_calls.append((tx_id, category, source, confidence))
        if tx_id not in self._store:
            raise KeyError(tx_id)
        existing = self._store[tx_id]
        self._store[tx_id] = existing.model_copy(
            update={
                "category": category,
                "category_source": source,
                "category_confidence": confidence,
            }
        )

    async def get(self, tx_id: str) -> Transaction | None:
        return self._store.get(tx_id)

    # Test-only helpers (not part of the port).
    def all(self) -> list[Transaction]:
        return list(self._store.values())

    def get_sync(self, tx_id: str) -> Transaction | None:
        """Synchronous version used in test assertions."""
        return self._store.get(tx_id)
