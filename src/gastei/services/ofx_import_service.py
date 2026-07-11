"""OFXImportService — manual statement import (ARCHITECTURE.md §7.4).

Used as a fallback for banks that aren't on Open Finance, or to backfill
historical data. Pipeline:

1. Parse the OFX file. If ``account_id`` is omitted, auto-resolve the target
   account from the file's ``BANKID``/``ACCTID`` (creating ``Item`` and
   ``Account`` rows if they don't exist yet).
2. Generate canonical ``Transaction`` rows with deterministic SHA-256 IDs so
   re-imports never duplicate.
3. Upsert through the ``TransactionRepository``.
4. If a ``Classifier`` is wired in, categorize the newly-inserted transactions.
"""

from __future__ import annotations

import hashlib
import io
import logging
from datetime import date as date_t
from datetime import datetime
from typing import Any

import ofxparse

from gastei.domain.ports import Classifier, TransactionRepository
from gastei.repositories.account_repo import AccountRepository, ItemRepository
from gastei.schemas.import_result import ImportResult
from gastei.schemas.ofx import OFXFingerprint
from gastei.schemas.transaction import AccountDTO, ItemDTO, Transaction
from gastei.utils.ofx_inspector import inspect_ofx

logger = logging.getLogger(__name__)


def _stable_id(account_id: str, tx_date: date_t, amount: float, description: str) -> str:
    """Deterministic SHA-256 over the fields that uniquely identify a transaction.

    Using ``amount`` with 2 decimal places avoids float-drift instability;
    normalising ``description`` (strip + lower) keeps re-imports stable across
    whitespace and case differences in the source file.
    """
    payload = f"{account_id}|{tx_date.isoformat()}|{amount:.2f}|{description.strip().lower()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _coerce_date(raw: Any) -> date_t:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date_t):
        return raw
    raise ValueError(f"Unexpected OFX date: {raw!r}")


def _pick_description(tx: Any) -> tuple[str, str | None]:
    """Returns ``(description, description_raw)``.

    Prefers ``payee`` (the ``NAME`` field in OFX) — typically the merchant —
    over ``memo`` (free text). When ``payee`` is missing, falls back to ``memo``.
    """
    payee = (getattr(tx, "payee", None) or "").strip()
    memo = (getattr(tx, "memo", None) or "").strip()

    if payee:
        return payee, memo or None
    if memo:
        return memo, None
    return "<no description>", None


class OFXImportService:
    def __init__(
        self,
        repo: TransactionRepository,
        classifier: Classifier | None = None,
        item_repo: ItemRepository | None = None,
        account_repo: AccountRepository | None = None,
    ) -> None:
        self._repo = repo
        self._classifier = classifier
        self._item_repo = item_repo
        self._account_repo = account_repo

    async def import_bytes(
        self,
        file_bytes: bytes,
        account_id: str | None = None,
    ) -> ImportResult:
        """Import an OFX file. If ``account_id`` is None, auto-resolve from the file fingerprint."""
        if account_id is None:
            account_id = self._resolve_account_from_ofx(file_bytes)

        try:
            parsed = ofxparse.OfxParser.parse(io.BytesIO(file_bytes))
        except Exception as exc:
            raise ValueError(f"Invalid OFX: {exc}") from exc

        txs: list[Transaction] = []
        seen_ids: set[str] = set()

        for ofx_account in parsed.accounts:
            statement = getattr(ofx_account, "statement", None)
            if statement is None:
                continue
            for raw_tx in statement.transactions:
                tx_date = _coerce_date(raw_tx.date)
                amount = float(raw_tx.amount)
                description, description_raw = _pick_description(raw_tx)

                tx_id = _stable_id(account_id, tx_date, amount, description)
                if tx_id in seen_ids:
                    # Same transaction duplicated within the same OFX file; skip the second one.
                    continue
                seen_ids.add(tx_id)

                txs.append(
                    Transaction(
                        id=tx_id,
                        account_id=account_id,
                        date=tx_date,
                        amount=amount,
                        description=description,
                        description_raw=description_raw,
                    )
                )

        if not txs:
            return ImportResult(imported=0, duplicates=0)

        existing_before = await self._existing_ids(txs)
        new_txs = [tx for tx in txs if tx.id not in existing_before]

        inserted, updated = await self._repo.upsert_many(txs)

        if self._classifier is not None and new_txs:
            await self._classify_and_persist(new_txs)

        return ImportResult(imported=inserted, duplicates=updated)

    # ------------------------------------------------------------------
    # Auto-resolve the target account from the file's metadata
    # ------------------------------------------------------------------

    def _resolve_account_from_ofx(self, file_bytes: bytes) -> str:
        """Inspect the OFX and return the corresponding account id.

        Creates ``Item`` and ``Account`` rows on demand. Requires the
        repositories to be wired in; otherwise raises ``ValueError`` asking
        for an explicit ``account_id``.
        """
        if self._item_repo is None or self._account_repo is None:
            raise ValueError(
                "account_id not provided and auto-resolve unavailable "
                "(item_repo / account_repo were not wired in)."
            )

        fp = inspect_ofx(file_bytes)
        if not fp.bank_id or not fp.account_id:
            raise ValueError(
                "OFX is missing BANKID / ACCTID — auto-resolve is not possible. "
                "Provide account_id explicitly."
            )

        # Item id = "ofx-<bank_id>" (stable, 1 item per bank).
        item_id = f"ofx-{fp.bank_id}"
        institution_name = fp.bank_name or f"Bank {fp.bank_id}"

        self._item_repo.upsert(
            ItemDTO(
                external_id=item_id,
                connector_id=int(fp.bank_id) if fp.bank_id.isdigit() else 0,
                institution_name=institution_name,
                status="UPDATED",
            )
        )

        # Account id = "ofx-<bank_id>-<account_id>" (1 account per (bank, account_id) pair).
        # Credit card and checking statements naturally become separate accounts
        # because their ACCTIDs differ in the OFX.
        account_id = f"ofx-{fp.bank_id}-{fp.account_id}".lower().replace(" ", "")
        kind_label = "Cartão" if fp.account_kind == "credit_card" else "Conta"
        account_type = "CREDIT" if fp.account_kind == "credit_card" else "CHECKING"

        self._account_repo.upsert(
            AccountDTO(
                external_id=account_id,
                item_external_id=item_id,
                type=account_type,
                name=f"{institution_name} {kind_label}",
                number=fp.account_id,
                balance=0.0,  # OFX does not carry a trustworthy balance; Pluggy sync would.
            )
        )

        logger.info(
            "Auto-resolved OFX → item=%s account=%s (%s)",
            item_id,
            account_id,
            institution_name,
        )
        return account_id

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _existing_ids(self, txs: list[Transaction]) -> set[str]:
        if not txs:
            return set()
        account_ids = {tx.account_id for tx in txs}
        existing: set[str] = set()
        for acc_id in account_ids:
            current = await self._repo.list_by_account(acc_id)
            existing.update(t.id for t in current)
        return existing

    async def _classify_and_persist(self, new_txs: list[Transaction]) -> None:
        assert self._classifier is not None
        results = await self._classifier.classify_batch(new_txs, examples=[])
        for r in results:
            await self._repo.update_category(
                tx_id=r.transaction_id,
                category=r.category,
                source=r.source,
                confidence=r.confidence,
            )

    # Public façade used by the inspector endpoint.
    @staticmethod
    def inspect(file_bytes: bytes) -> OFXFingerprint:
        return inspect_ofx(file_bytes)
