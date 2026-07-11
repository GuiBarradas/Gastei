"""DTO returned by import services (OFX today, possibly CSV tomorrow)."""

from pydantic import BaseModel, Field


class ImportResult(BaseModel):
    imported: int = Field(ge=0, description="Number of new transactions inserted")
    duplicates: int = Field(ge=0, description="Number that already existed (idempotency)")
    errors: list[str] = Field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return self.imported + self.duplicates
