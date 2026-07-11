"""PluggyBankConnector — adapter implementing the ``BankConnector`` port via ``PluggyClient``.

Translates Pluggy's JSON envelopes (camelCase, some nested fields) into the
canonical DTOs the domain consumes. Handles full pagination for
``list_transactions``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from gastei.clients.pluggy_client import PluggyClient
from gastei.schemas.transaction import (
    AccountDTO,
    ItemDTO,
    TransactionDTO,
)


class PluggyBankConnector:
    """Implements ``gastei.domain.ports.BankConnector`` over ``PluggyClient``."""

    def __init__(self, client: PluggyClient) -> None:
        self._client = client

    async def list_items(self) -> list[ItemDTO]:
        items = await self._client.list_items()
        return [self._to_item_dto(i) for i in items]

    async def list_accounts(self, item_id: str) -> list[AccountDTO]:
        accounts = await self._client.list_accounts(item_id)
        return [self._to_account_dto(a) for a in accounts]

    async def list_transactions(
        self,
        account_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[TransactionDTO]:
        df = date_from.isoformat() if date_from else None
        dt_ = date_to.isoformat() if date_to else None

        all_dtos: list[TransactionDTO] = []
        page = 1
        while True:
            data = await self._client.list_transactions(
                account_id, date_from=df, date_to=dt_, page=page
            )
            results = data.get("results", [])
            for tx in results:
                all_dtos.append(self._to_tx_dto(tx))

            total_pages = data.get("totalPages") or 1
            if page >= total_pages:
                break
            page += 1
        return all_dtos

    async def trigger_sync(self, item_id: str) -> None:
        await self._client.trigger_sync(item_id)

    # ------------------------------------------------------------------
    # Mappers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_item_dto(raw: dict[str, Any]) -> ItemDTO:
        connector = raw.get("connector") or {}
        return ItemDTO(
            external_id=raw["id"],
            connector_id=int(connector.get("id", 0)),
            institution_name=connector.get("name") or raw.get("institutionName") or "?",
            status=raw.get("status", "UPDATED"),
            last_synced_at=_parse_dt(raw.get("lastUpdatedAt")),
        )

    @staticmethod
    def _to_account_dto(raw: dict[str, Any]) -> AccountDTO:
        return AccountDTO(
            external_id=raw["id"],
            item_external_id=raw["itemId"],
            type=raw.get("type", "CHECKING"),
            subtype=raw.get("subtype"),
            name=raw.get("name") or raw.get("marketingName") or "Account",
            number=raw.get("number"),
            balance=float(raw.get("balance") or 0.0),
            currency_code=raw.get("currencyCode", "BRL"),
        )

    @staticmethod
    def _to_tx_dto(raw: dict[str, Any]) -> TransactionDTO:
        merchant_block = raw.get("merchant") or {}
        payment_block = raw.get("paymentData") or {}
        description = raw.get("description") or raw.get("descriptionRaw") or "<no description>"
        return TransactionDTO(
            external_id=raw["id"],
            account_external_id=raw["accountId"],
            date=_parse_date(raw["date"]),
            amount=float(raw["amount"]),
            description=description,
            description_raw=raw.get("descriptionRaw"),
            merchant_name=merchant_block.get("name"),
            pluggy_category=raw.get("category"),
            payment_method=payment_block.get("paymentMethod"),
        )


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        # Pluggy returns ISO 8601 with a trailing 'Z'.
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _parse_date(raw: str | datetime | date) -> date:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    # ISO string — may include a full timestamp.
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
