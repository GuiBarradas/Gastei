"""FakeClassifier — substring-driven, scriptable classification."""

from __future__ import annotations

from gastei.schemas.categorization import (
    CategorizationResult,
    CategorizationSource,
    Example,
)
from gastei.schemas.transaction import Transaction


class FakeClassifier:
    """Implements ``gastei.domain.ports.Classifier``.

    Behavior: for each transaction, finds the first key in ``mapping`` that
    appears (case-insensitive) in the description. Falls back to
    ``default_category`` if no key matches. Useful for simulating both rules
    and LLM responses in tests.
    """

    def __init__(
        self,
        mapping: dict[str, str] | None = None,
        default_category: str = "outros.diversos",
        source: CategorizationSource = "llm",
        confidence: float = 0.9,
        raises: Exception | None = None,
    ) -> None:
        self._mapping = {k.lower(): v for k, v in (mapping or {}).items()}
        self._default = default_category
        self._source: CategorizationSource = source
        self._confidence = confidence
        self._raises = raises
        self.calls: list[tuple[list[Transaction], list[Example]]] = []

    async def classify_batch(
        self, txs: list[Transaction], examples: list[Example]
    ) -> list[CategorizationResult]:
        self.calls.append((list(txs), list(examples)))
        if self._raises is not None:
            raise self._raises
        results: list[CategorizationResult] = []
        for tx in txs:
            desc = tx.description.lower()
            category = next(
                (cat for key, cat in self._mapping.items() if key in desc),
                self._default,
            )
            results.append(
                CategorizationResult(
                    transaction_id=tx.id,
                    category=category,
                    source=self._source,
                    confidence=self._confidence,
                    reasoning=f"fake match on '{desc[:40]}'",
                )
            )
        return results
