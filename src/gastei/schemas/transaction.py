"""Transaction / account / item DTOs.

``Transaction`` is the canonical shape used inside the domain. ``TransactionDTO``,
``AccountDTO``, and ``ItemDTO`` are the raw shapes returned by a ``BankConnector``
(Pluggy today; potentially Belvo or another provider tomorrow) — provider-neutral.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CategorySource = Literal["rule", "llm", "user", "pluggy"]


class Transaction(BaseModel):
    """Canonical domain shape. Repositories translate ORM rows to/from this."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    date: date
    amount: float
    description: str
    description_raw: str | None = None
    merchant_name: str | None = None
    category: str | None = None
    category_source: CategorySource | None = None
    category_confidence: float | None = Field(default=None, ge=0, le=1)
    pluggy_category: str | None = None
    payment_method: str | None = None


class TransactionDTO(BaseModel):
    """Raw shape from a ``BankConnector``. Services convert this into ``Transaction``
    before persisting."""

    external_id: str
    account_external_id: str
    date: date
    amount: float
    description: str
    description_raw: str | None = None
    merchant_name: str | None = None
    pluggy_category: str | None = None
    payment_method: str | None = None


class AccountDTO(BaseModel):
    external_id: str
    item_external_id: str
    type: str
    subtype: str | None = None
    name: str
    number: str | None = None
    balance: float
    currency_code: str = "BRL"


class ItemDTO(BaseModel):
    external_id: str
    connector_id: int
    institution_name: str
    status: str
    last_synced_at: datetime | None = None
