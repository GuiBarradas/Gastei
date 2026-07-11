"""DTOs for the OFX inspector (preview before importing)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel

AccountKind = Literal["checking", "credit_card", "unknown"]


class OFXFingerprint(BaseModel):
    """Metadata extracted from an OFX file without persisting anything."""

    bank_id: str | None = None
    bank_name: str | None = None
    account_id: str | None = None
    account_kind: AccountKind = "unknown"
    transaction_count: int = 0
    date_from: date | None = None
    date_to: date | None = None

    @property
    def label(self) -> str:
        bank = self.bank_name or "Unknown bank"
        acc = self.account_id or "?"
        kind = "credit card" if self.account_kind == "credit_card" else "account"
        return f"{bank} ({kind} {acc})"
