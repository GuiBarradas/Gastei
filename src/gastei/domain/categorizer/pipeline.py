"""CategorizationPipeline — orchestrates rules (stage 1) and LLM (stage 2).

Implements the ``Classifier`` port itself so it can be wired anywhere a
``Classifier`` is expected (for instance, into ``OFXImportService``). The
``examples`` argument from the port signature is ignored by design: the
pipeline fetches the most relevant examples from its ``ExampleStore``
internally, which is the only strategy that makes sense at this layer.

Degraded mode: "deterministic before probabilistic" (ARCHITECTURE.md §2) also
governs failure. If the LLM stage raises (provider 503/429, quota, network),
the pipeline keeps the stage-1 rule results instead of failing the whole batch,
and opens a circuit breaker: for the rest of this instance's lifetime the LLM
is not called again. Instances are per-request (see ``api.deps``), so the
breaker never sticks across requests.
"""

from __future__ import annotations

import logging

from gastei.domain.categorizer.rule_engine import RuleEngine
from gastei.domain.ports import Classifier, ExampleStore
from gastei.schemas.categorization import CategorizationResult, Example
from gastei.schemas.transaction import Transaction

logger = logging.getLogger(__name__)


class CategorizationPipeline:
    def __init__(
        self,
        rule_engine: RuleEngine,
        classifier: Classifier,
        example_store: ExampleStore,
        examples_k: int = 20,
    ) -> None:
        self._rule_engine = rule_engine
        self._classifier = classifier
        self._example_store = example_store
        self._examples_k = examples_k
        self._llm_unavailable = False

    async def classify_batch(
        self,
        txs: list[Transaction],
        examples: list[Example],
    ) -> list[CategorizationResult]:
        if not txs:
            return []

        # Stage 1 — rules (short-circuit, confidence=1.0)
        results: list[CategorizationResult] = []
        to_llm: list[Transaction] = []

        for tx in txs:
            rule = self._rule_engine.match(tx)
            if rule is not None:
                results.append(
                    CategorizationResult(
                        transaction_id=tx.id,
                        category=rule.category,
                        source="rule",
                        confidence=1.0,
                        reasoning=f"rule:{rule.pattern_type}:{rule.pattern}",
                    )
                )
            else:
                to_llm.append(tx)

        # Stage 2 — LLM (only if anything is left and the breaker is closed)
        if to_llm and not self._llm_unavailable:
            relevant_examples = self._example_store.most_relevant(to_llm, k=self._examples_k)
            try:
                llm_results = await self._classifier.classify_batch(
                    to_llm, examples=relevant_examples
                )
            except Exception:
                self._llm_unavailable = True
                logger.warning(
                    "LLM stage failed for %d transaction(s) — returning rule results only "
                    "and skipping the LLM for the rest of this run.",
                    len(to_llm),
                    exc_info=True,
                )
            else:
                results.extend(llm_results)

        return results
