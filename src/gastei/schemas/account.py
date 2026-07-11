"""Account / Item DTOs — outbound shapes used in API responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    item_id: str
    type: str
    subtype: str | None = None
    name: str
    number: str | None = None
    balance: float
    currency_code: str = "BRL"
    updated_at: datetime


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    connector_id: int
    institution_name: str
    status: str
    last_synced_at: datetime | None = None
    next_auto_sync_at: datetime | None = None
    created_at: datetime
