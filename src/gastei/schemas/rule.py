"""Pydantic DTO for a categorization rule (mirrors the ORM in ``models/rule.py``)."""

from typing import Literal

from pydantic import BaseModel, Field

PatternType = Literal["substring", "regex", "merchant_exact"]


class Rule(BaseModel):
    pattern: str = Field(min_length=1)
    pattern_type: PatternType
    category: str
    priority: int = 100
    enabled: bool = True
    id: int | None = None
