"""FakeBankConnector — stands in for Pluggy in tests."""

from __future__ import annotations

from datetime import date

from gastei.schemas.transaction import (
    AccountDTO,
    ItemDTO,
    TransactionDTO,
)


class FakeBankConnector:
    """Implements ``gastei.domain.ports.BankConnector`` in memory.

    Use the constructor arguments to seed data, and ``triggered_syncs`` for
    assertions that ``trigger_sync`` was called.
    """

    def __init__(
        self,
        items: list[ItemDTO] | None = None,
        accounts_by_item: dict[str, list[AccountDTO]] | None = None,
        transactions_by_account: dict[str, list[TransactionDTO]] | None = None,
    ) -> None:
        self._items: list[ItemDTO] = list(items) if items else []
        self._accounts: dict[str, list[AccountDTO]] = dict(accounts_by_item or {})
        self._transactions: dict[str, list[TransactionDTO]] = dict(transactions_by_account or {})
        self.triggered_syncs: list[str] = []

    async def list_items(self) -> list[ItemDTO]:
        return list(self._items)

    async def list_accounts(self, item_id: str) -> list[AccountDTO]:
        return list(self._accounts.get(item_id, []))

    async def list_transactions(
        self,
        account_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[TransactionDTO]:
        result = list(self._transactions.get(account_id, []))
        if date_from is not None:
            result = [tx for tx in result if tx.date >= date_from]
        if date_to is not None:
            result = [tx for tx in result if tx.date <= date_to]
        return result

    async def trigger_sync(self, item_id: str) -> None:
        self.triggered_syncs.append(item_id)
