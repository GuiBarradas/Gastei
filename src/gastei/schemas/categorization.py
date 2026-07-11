"""DTOs for the categorization pipeline."""

from typing import Literal

from pydantic import BaseModel, Field

CategorizationSource = Literal["rule", "llm", "user", "pluggy"]
ExampleSource = Literal["user_correction", "manual_seed"]


class CategorizationResult(BaseModel):
    transaction_id: str
    category: str
    source: CategorizationSource
    confidence: float = Field(ge=0, le=1)
    reasoning: str | None = Field(default=None, max_length=500)


class Example(BaseModel):
    """Few-shot example for the LLM. Comes from user corrections or a manual seed."""

    description: str
    amount: float | None = None
    category: str
    source: ExampleSource


class TxClassificationRaw(BaseModel):
    """Raw LLM tool-use input. The service converts this into ``CategorizationResult``."""

    transaction_id: str
    category: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str = Field(default="", max_length=500)


class BatchClassification(BaseModel):
    """Schema for the ``record_classifications`` tool the LLM populates."""

    classifications: list[TxClassificationRaw]
