"""Read + upsert repositories for ``Account`` and ``Item``.

Intentionally not behind a Protocol yet. These methods are simple and there
is no test scenario that calls for substituting them — the integration
tests insert ORM rows directly. If a service needs to mock these, we
promote them to a Protocol then.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from gastei.models.account import Account as AccountORM
from gastei.models.item import Item as ItemORM
from gastei.schemas.transaction import AccountDTO, ItemDTO


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[AccountORM]:
        return list(self._session.scalars(select(AccountORM)).all())

    def upsert(self, dto: AccountDTO) -> AccountORM:
        existing = self._session.get(AccountORM, dto.external_id)
        if existing is None:
            existing = AccountORM(id=dto.external_id, item_id=dto.item_external_id)
            self._session.add(existing)
        existing.type = dto.type
        existing.subtype = dto.subtype
        existing.name = dto.name
        existing.number = dto.number
        existing.balance = dto.balance
        existing.currency_code = dto.currency_code
        existing.updated_at = datetime.now()
        self._session.flush()
        return existing


class ItemRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[ItemORM]:
        return list(self._session.scalars(select(ItemORM)).all())

    def upsert(self, dto: ItemDTO) -> ItemORM:
        existing = self._session.get(ItemORM, dto.external_id)
        if existing is None:
            existing = ItemORM(id=dto.external_id)
            self._session.add(existing)
        existing.connector_id = dto.connector_id
        existing.institution_name = dto.institution_name
        existing.status = dto.status
        existing.last_synced_at = dto.last_synced_at
        self._session.flush()
        return existing
