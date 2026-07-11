"""DTO for the category taxonomy — read side, consumed by UI dropdowns."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    parent_code: str | None = None
    label: str
    icon: str | None = None
    color: str | None = None
    is_income: bool = False
    is_investment: bool = False
    is_transfer: bool = False
