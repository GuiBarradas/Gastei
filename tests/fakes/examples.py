"""FakeExampleStore — in-memory list ordered by insertion (most recent at the end)."""

from __future__ import annotations

from gastei.schemas.categorization import Example
from gastei.schemas.transaction import Transaction


class FakeExampleStore:
    """Implements ``gastei.domain.ports.ExampleStore`` in memory.

    Relevance strategy: top-K most recent (mirrors ARCHITECTURE.md §7.2).
    """

    def __init__(self, seed: list[Example] | None = None) -> None:
        self._examples: list[Example] = list(seed) if seed else []

    def most_relevant(self, txs: list[Transaction], k: int = 20) -> list[Example]:
        # ``txs`` is ignored under this simple strategy; kept for port compatibility.
        _ = txs
        return list(reversed(self._examples[-k:]))

    def add(self, example: Example) -> None:
        self._examples.append(example)

    # Helpers
    def all(self) -> list[Example]:
        return list(self._examples)
