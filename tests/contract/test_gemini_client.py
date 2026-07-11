"""``GeminiLLMClient`` contract test — real call against the free tier.

Skipped by default. To run::

    uv run pytest -m contract tests/contract/test_gemini_client.py

Required: ``GOOGLE_API_KEY`` environment variable (or ``.env`` entry).
Obtain one at https://aistudio.google.com/apikey (no card required, 1500
requests/day on the free tier).
"""

from __future__ import annotations

import pytest
from google.genai import errors as genai_errors

from gastei.clients.gemini_client import GeminiLLMClient
from gastei.config import get_settings
from gastei.domain.categorizer.llm_classifier import LLMClassifier
from gastei.schemas.transaction import Transaction

pytestmark = [
    pytest.mark.contract,
    pytest.mark.skipif(
        not get_settings().google_api_key,
        reason="Sem GOOGLE_API_KEY (.env ou env var)",
    ),
]


SMALL_TAXONOMY = [
    "alimentacao.delivery",
    "transporte.app",
    "lazer.streaming",
    "outros.diversos",
]


async def test_classify_via_gemini_free_tier() -> None:
    """E2E: 3 transações claras → categorias corretas via Gemini Flash."""
    from datetime import date

    llm = GeminiLLMClient()
    clf = LLMClassifier(
        llm=llm,
        taxonomy=SMALL_TAXONOMY,
        model=get_settings().gemini_model_fast,
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
            id="t2", account_id="a", date=date(2026, 5, 2), amount=-30.0, description="UBER *TRIP"
        ),
        Transaction(
            id="t3", account_id="a", date=date(2026, 5, 3), amount=-29.90, description="NETFLIX.COM"
        ),
    ]

    try:
        results = await clf.classify_batch(txs, examples=[])
    except genai_errors.APIError as exc:
        # Capacity problems on the free tier are not contract drift — a 404
        # (retired model) or schema mismatch must still fail loudly.
        if exc.code in (429, 503):
            pytest.skip(f"Gemini free tier temporarily unavailable (HTTP {exc.code})")
        raise

    by_id = {r.transaction_id: r for r in results}
    assert by_id["t1"].category == "alimentacao.delivery"
    assert by_id["t2"].category == "transporte.app"
    assert by_id["t3"].category == "lazer.streaming"
