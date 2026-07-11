"""Pydantic DTOs — canonical domain shapes. No SQLAlchemy dependency."""

from gastei.schemas.categorization import (
    BatchClassification,
    CategorizationResult,
    CategorizationSource,
    Example,
    ExampleSource,
    TxClassificationRaw,
)
from gastei.schemas.import_result import ImportResult
from gastei.schemas.llm import LLMResponse, LLMToolUse, StopReason
from gastei.schemas.rule import PatternType, Rule
from gastei.schemas.transaction import (
    AccountDTO,
    CategorySource,
    ItemDTO,
    Transaction,
    TransactionDTO,
)

__all__ = [
    "AccountDTO",
    "BatchClassification",
    "CategorizationResult",
    "CategorizationSource",
    "CategorySource",
    "Example",
    "ExampleSource",
    "ImportResult",
    "ItemDTO",
    "LLMResponse",
    "LLMToolUse",
    "PatternType",
    "Rule",
    "StopReason",
    "Transaction",
    "TransactionDTO",
    "TxClassificationRaw",
]
