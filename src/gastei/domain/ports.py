"""Ports — Protocols that define the contracts between the core and the adapters.

These are the architectural seam (see ARCHITECTURE.md §7.0). The domain
defines the interface; adapters in ``gastei.clients``, ``gastei.repositories``,
and ``gastei.api`` implement it. Dependency inversion is enforced socially:
if a module under ``gastei.domain`` or ``gastei.services`` imports from
``gastei.clients``, ``gastei.repositories``, or ``sqlalchemy``, that is an
architectural bug.
"""

from datetime import date
from typing import Any, Protocol, runtime_checkable

from gastei.schemas.categorization import CategorizationResult, Example
from gastei.schemas.llm import LLMResponse
from gastei.schemas.transaction import (
    AccountDTO,
    ItemDTO,
    Transaction,
    TransactionDTO,
)


@runtime_checkable
class TransactionRepository(Protocol):
    """Persistence for canonical transactions."""

    async def upsert_many(self, txs: list[Transaction]) -> tuple[int, int]:
        """Insert or update by id. Returns ``(inserted_count, updated_count)``."""
        ...

    async def get(self, tx_id: str) -> Transaction | None: ...

    async def list_by_account(
        self,
        account_id: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[Transaction]: ...

    async def list_uncategorized(self, limit: int = 100) -> list[Transaction]: ...

    async def update_category(
        self,
        tx_id: str,
        category: str,
        source: str,
        confidence: float | None = None,
    ) -> None: ...


@runtime_checkable
class ExampleStore(Protocol):
    """Few-shot store. The current strategy returns the K most recent examples."""

    def most_relevant(self, txs: list[Transaction], k: int = 20) -> list[Example]: ...

    def add(self, example: Example) -> None: ...


@runtime_checkable
class Classifier(Protocol):
    """A categorizer over a batch of transactions (rule-based, LLM-based, or hybrid)."""

    async def classify_batch(
        self, txs: list[Transaction], examples: list[Example]
    ) -> list[CategorizationResult]: ...


class LLMUnavailableError(RuntimeError):
    """The LLM provider failed (rate limit, capacity, network, auth).

    Adapters translate SDK-specific errors into this so callers can react
    without importing provider SDKs.
    """


@runtime_checkable
class LLMClient(Protocol):
    """Provider-agnostic adapter over an LLM SDK.

    The interface stays narrow on purpose; SDK-specific quirks live inside
    the concrete adapter. Provider failures surface as ``LLMUnavailableError``.
    """

    async def messages_create(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse: ...


@runtime_checkable
class BankConnector(Protocol):
    """Open Finance aggregator. Currently backed by Pluggy; Belvo or another
    provider could be plugged in by writing a second adapter."""

    async def list_items(self) -> list[ItemDTO]: ...

    async def list_accounts(self, item_id: str) -> list[AccountDTO]: ...

    async def list_transactions(
        self,
        account_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[TransactionDTO]: ...

    async def trigger_sync(self, item_id: str) -> None: ...
