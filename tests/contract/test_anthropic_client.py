"""``AnthropicLLMClient`` contract test — real API call.

Skipped by default (it costs money). To run::

    uv run pytest -m contract tests/contract/test_anthropic_client.py

Required: ``ANTHROPIC_API_KEY`` environment variable (or ``.env`` entry).
"""

from __future__ import annotations

import pytest

from gastei.clients.llm_client import AnthropicLLMClient
from gastei.config import get_settings
from gastei.domain.categorizer.llm_classifier import LLMClassifier
from gastei.schemas.transaction import Transaction

pytestmark = [
    pytest.mark.contract,
    pytest.mark.skipif(
        not get_settings().anthropic_api_key,
        reason="No ANTHROPIC_API_KEY in .env or environment",
    ),
]


SMALL_TAXONOMY = [
    "alimentacao.delivery",
    "transporte.app",
    "lazer.streaming",
    "outros.diversos",
]


async def test_classify_a_few_transactions_against_real_haiku() -> None:
    """E2E: three obvious transactions should come back correctly categorized."""
    from datetime import date

    llm = AnthropicLLMClient()
    clf = LLMClassifier(
        llm=llm,
        taxonomy=SMALL_TAXONOMY,
        model="claude-haiku-4-5",
        max_tokens=1024,
    )

    txs = [
        Transaction(
            id="t1",
            account_id="a",
            date=date(2026, 5, 1),
            amount=-50.0,
            description="IFOOD *RESTAURANTE LTDA",
        ),
        Transaction(
            id="t2",
            account_id="a",
            date=date(2026, 5, 2),
            amount=-30.0,
            description="UBER *TRIP HELP.UBER.COM",
        ),
        Transaction(
            id="t3", account_id="a", date=date(2026, 5, 3), amount=-29.90, description="NETFLIX.COM"
        ),
    ]

    results = await clf.classify_batch(txs, examples=[])

    by_id = {r.transaction_id: r for r in results}
    assert by_id["t1"].category == "alimentacao.delivery"
    assert by_id["t2"].category == "transporte.app"
    assert by_id["t3"].category == "lazer.streaming"
    # All three should come back with high confidence
    for r in results:
        assert r.confidence >= 0.7, f"Low confidence on an obvious sample: {r}"
