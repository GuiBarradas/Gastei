"""SyncService — pulls data through a ``BankConnector`` and persists it.

Flow (ARCHITECTURE.md §4, "Sync from a bank"):

1. ``bank.list_items()`` → upsert items into the database.
2. For each item: ``list_accounts()`` → upsert accounts.
3. For each account: ``list_transactions()`` → convert DTOs to ``Transaction``
   and upsert through ``TransactionRepository``.
4. Optionally: classify the newly-inserted transactions.
"""

from __future__ import annotations

import logging

from gastei.domain.ports import (
    BankConnector,
    Classifier,
    TransactionRepository,
)
from gastei.repositories.account_repo import AccountRepository, ItemRepository
from gastei.schemas.sync import SyncResult
from gastei.schemas.transaction import Transaction, TransactionDTO

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(
        self,
        bank: BankConnector,
        tx_repo: TransactionRepository,
        account_repo: AccountRepository,
        item_repo: ItemRepository,
        classifier: Classifier | None = None,
    ) -> None:
        self._bank = bank
        self._tx_repo = tx_repo
        self._account_repo = account_repo
        self._item_repo = item_repo
        self._classifier = classifier

    async def sync_all(self) -> SyncResult:
        items = await self._bank.list_items()
        items_synced = 0
        accounts_synced = 0
        total_imported = 0
        total_duplicates = 0
        total_categorized = 0
        errors: list[str] = []

        for item in items:
            try:
                self._item_repo.upsert(item)
                items_synced += 1
            except Exception as exc:
                errors.append(f"item {item.external_id}: {exc}")
                continue

            try:
                accounts = await self._bank.list_accounts(item.external_id)
            except Exception as exc:
                errors.append(f"list_accounts {item.external_id}: {exc}")
                continue

            for account in accounts:
                try:
                    self._account_repo.upsert(account)
                    accounts_synced += 1
                except Exception as exc:
                    errors.append(f"account {account.external_id}: {exc}")
                    continue

                try:
                    tx_dtos = await self._bank.list_transactions(account.external_id)
                except Exception as exc:
                    errors.append(f"list_transactions {account.external_id}: {exc}")
                    continue

                txs = [_dto_to_transaction(dto) for dto in tx_dtos]
                # Snapshot of pre-existing ids so we can tell which transactions are new
                # and only classify those (not the ones being re-upserted).
                existing_before = await self._existing_ids(account.external_id, txs)
                new_txs = [tx for tx in txs if tx.id not in existing_before]

                inserted, updated = await self._tx_repo.upsert_many(txs)
                total_imported += inserted
                total_duplicates += updated

                # Optional categorization, only on the genuinely new rows.
                if self._classifier is not None and new_txs:
                    try:
                        results = await self._classifier.classify_batch(new_txs, examples=[])
                        for r in results:
                            await self._tx_repo.update_category(
                                tx_id=r.transaction_id,
                                category=r.category,
                                source=r.source,
                                confidence=r.confidence,
                            )
                        total_categorized += len(results)
                    except Exception as exc:
                        errors.append(f"classify {account.external_id}: {exc}")

        return SyncResult(
            items_synced=items_synced,
            accounts_synced=accounts_synced,
            transactions_imported=total_imported,
            transactions_duplicates=total_duplicates,
            transactions_categorized=total_categorized,
            errors=errors,
        )

    async def _existing_ids(self, account_id: str, txs: list[Transaction]) -> set[str]:
        if not txs:
            return set()
        current = await self._tx_repo.list_by_account(account_id)
        return {t.id for t in current}


def _dto_to_transaction(dto: TransactionDTO) -> Transaction:
    """Convert a ``TransactionDTO`` (Pluggy or OFX) into a canonical ``Transaction``.

    Reuses the DTO's ``external_id`` as the transaction id — Pluggy guarantees
    its ``transactionId`` is stable, and OFX uses a deterministic hash.
    """
    return Transaction(
        id=dto.external_id,
        account_id=dto.account_external_id,
        date=dto.date,
        amount=dto.amount,
        description=dto.description,
        description_raw=dto.description_raw,
        merchant_name=dto.merchant_name,
        pluggy_category=dto.pluggy_category,
        payment_method=dto.payment_method,
    )
