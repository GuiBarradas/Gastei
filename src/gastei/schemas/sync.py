"""DTO for the result of a sync run."""

from pydantic import BaseModel, Field


class SyncResult(BaseModel):
    items_synced: int = Field(ge=0)
    accounts_synced: int = Field(ge=0)
    transactions_imported: int = Field(ge=0)
    transactions_duplicates: int = Field(ge=0)
    transactions_categorized: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)
