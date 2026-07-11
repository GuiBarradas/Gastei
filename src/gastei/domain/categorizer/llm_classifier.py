"""LLMClassifier — stage two of the categorization pipeline (ARCHITECTURE.md §7.2).

Implements the ``Classifier`` port using an ``LLMClient``. Strategy:

1. Build a system prompt containing the full taxonomy (stable, prompt-cache friendly).
2. Build a user message containing the batch of transactions and the few-shot examples.
3. Use Anthropic-style tool use to force the LLM to populate ``BatchClassification``.
4. Validate each item against the taxonomy; drop invalid items with a warning rather
   than failing the entire batch. Retry with feedback only if nothing valid came back.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from gastei.domain.ports import LLMClient
from gastei.schemas.categorization import (
    BatchClassification,
    CategorizationResult,
    Example,
)
from gastei.schemas.transaction import Transaction

logger = logging.getLogger(__name__)

TOOL_NAME = "record_classifications"


class LLMClassifier:
    def __init__(
        self,
        llm: LLMClient,
        taxonomy: list[str],
        model: str,
        max_retries: int = 2,
        max_tokens: int = 4096,
    ) -> None:
        self._llm = llm
        self._taxonomy = list(taxonomy)
        self._taxonomy_set = set(taxonomy)
        self._model = model
        self._max_retries = max_retries
        self._max_tokens = max_tokens
        self._tool_schema = self._build_tool_schema()

    async def classify_batch(
        self, txs: list[Transaction], examples: list[Example]
    ) -> list[CategorizationResult]:
        if not txs:
            return []

        system = self._build_system()
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": self._build_user_content(txs, examples)},
        ]

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            response = await self._llm.messages_create(
                model=self._model,
                system=system,
                messages=messages,
                tools=[self._tool_schema],
                max_tokens=self._max_tokens,
            )

            try:
                return self._parse_response(response)
            except ValueError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    # Surface the error to the model on the retry so it can adjust.
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"The previous response was invalid: {exc}. "
                                "Resubmit using only category codes from the taxonomy."
                            ),
                        }
                    )
                    continue
                raise

        # Defensive — the loop above always returns or raises.
        assert last_error is not None
        raise last_error

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_system(self) -> str:
        # The system prompt is in Portuguese because the categorization
        # taxonomy and the merchant patterns are Brazilian; aligning the
        # prompt language helps the model stay on task.
        taxonomy_lines = "\n".join(f"- {code}" for code in self._taxonomy)
        return (
            "Você é o categorizador de transações financeiras do Gastei.\n\n"
            "REGRAS:\n"
            "- Use SEMPRE a tool 'record_classifications' pra retornar.\n"
            "- A categoria DEVE ser um dos códigos abaixo, copiado exatamente.\n"
            "- Confidence reflete sua certeza (0.0 a 1.0). Use ≥0.8 quando a descrição "
            "é inequívoca; abaixo disso pra casos ambíguos.\n"
            "- Reasoning: 1 frase curta justificando.\n\n"
            f"TAXONOMIA VÁLIDA:\n{taxonomy_lines}\n"
        )

    def _build_user_content(self, txs: list[Transaction], examples: list[Example]) -> str:
        parts: list[str] = []

        if examples:
            parts.append("EXEMPLOS DE CATEGORIZAÇÕES PRÉVIAS (use como referência):")
            for ex in examples:
                amt = f" (R$ {ex.amount:.2f})" if ex.amount is not None else ""
                parts.append(f"- {ex.description!r}{amt} → {ex.category}")
            parts.append("")

        parts.append("TRANSAÇÕES A CATEGORIZAR:")
        for tx in txs:
            parts.append(
                f"- id={tx.id} | {tx.date.isoformat()} | R$ {tx.amount:.2f} | {tx.description!r}"
            )

        parts.append("")
        parts.append(
            "Para cada transação acima, chame a tool 'record_classifications' "
            "com uma classificação por id."
        )
        return "\n".join(parts)

    def _build_tool_schema(self) -> dict[str, Any]:
        # Hand-written (not ``model_json_schema()``): no $defs or Pydantic
        # internals leaking into the prompt.
        return {
            "name": TOOL_NAME,
            "description": "Records the categorization of a batch of transactions.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "classifications": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "transaction_id": {"type": "string"},
                                "category": {
                                    "type": "string",
                                    "description": "Exact code from the taxonomy.",
                                },
                                "confidence": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 1,
                                },
                                "reasoning": {
                                    "type": "string",
                                    "maxLength": 500,
                                },
                            },
                            "required": [
                                "transaction_id",
                                "category",
                                "confidence",
                                "reasoning",
                            ],
                        },
                    }
                },
                "required": ["classifications"],
            },
        }

    # ------------------------------------------------------------------
    # Parsing and validation
    # ------------------------------------------------------------------

    def _parse_response(self, response) -> list[CategorizationResult]:
        if not response.tool_uses:
            raise ValueError(
                "LLM did not call the 'record_classifications' tool. "
                f"stop_reason={response.stop_reason!r}, text={response.text[:200]!r}"
            )

        tool_use = response.tool_uses[0]
        if tool_use.name != TOOL_NAME:
            raise ValueError(f"Unexpected tool: {tool_use.name!r}")

        try:
            batch = BatchClassification.model_validate(tool_use.input)
        except ValidationError as exc:
            raise ValueError(f"LLM output failed Pydantic validation: {exc}") from exc

        # Tolerance: drop individual items whose category is outside the
        # taxonomy rather than killing the whole batch. We log this so the
        # operator can see when the model drifts.
        valid: list[CategorizationResult] = []
        invalid_codes: set[str] = set()
        for c in batch.classifications:
            if c.category not in self._taxonomy_set:
                invalid_codes.add(c.category)
                continue
            valid.append(
                CategorizationResult(
                    transaction_id=c.transaction_id,
                    category=c.category,
                    source="llm",
                    confidence=c.confidence,
                    reasoning=c.reasoning or None,
                )
            )

        if invalid_codes:
            logger.warning(
                "LLM returned %d categories outside the taxonomy: %s",
                len(invalid_codes),
                sorted(invalid_codes),
            )

        # If nothing came back valid, retry — possibly the model drifted entirely.
        if not valid and batch.classifications:
            raise ValueError(
                f"No valid classifications (all outside the taxonomy: {sorted(invalid_codes)})"
            )

        return valid
