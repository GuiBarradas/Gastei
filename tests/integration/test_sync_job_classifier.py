"""Regression: the sync job must be able to build its classifier outside FastAPI.

``run_sync_job`` used to call the DI wrapper ``get_classifier()`` bare. Outside
a request cycle, FastAPI does not resolve ``Depends`` defaults, so the wrapper
received raw ``Depends`` objects and crashed — swallowed by the job's broad
``except``, which made the scheduled sync fail silently on every run.
``build_classifier`` is the plain constructor both paths now share.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from gastei.api.deps import build_classifier
from gastei.config import get_settings
from gastei.domain.categorizer.pipeline import CategorizationPipeline
from gastei.schemas.llm import LLMResponse, LLMToolUse
from gastei.schemas.transaction import Transaction
from tests.fakes.llm import FakeLLMClient

pytestmark = pytest.mark.integration


def test_build_classifier_without_llm(db_session: Session) -> None:
    """No LLM configured → still returns a working (rules-only) pipeline."""
    clf = build_classifier(db_session, llm=None)
    assert isinstance(clf, CategorizationPipeline)


async def test_build_classifier_uses_fast_model(db_session: Session) -> None:
    """Classification runs on the *fast* model tier (ARCHITECTURE.md §7.2)."""
    fake = FakeLLMClient(
        responses=[
            LLMResponse(
                stop_reason="tool_use",
                tool_uses=[
                    LLMToolUse(
                        id="tu1",
                        name="record_classifications",
                        input={
                            "classifications": [
                                {
                                    "transaction_id": "t1",
                                    "category": "outros.diversos",
                                    "confidence": 0.5,
                                    "reasoning": "",
                                }
                            ]
                        },
                    )
                ],
            )
        ]
    )
    clf = build_classifier(db_session, llm=fake)

    tx = Transaction(
        id="t1",
        account_id="a",
        date=date(2026, 1, 1),
        amount=-10.0,
        description="XYZWQ COMERCIO DESCONHECIDO",  # matches no seed rule → goes to the LLM
    )
    results = await clf.classify_batch([tx], examples=[])

    settings = get_settings()
    expected = (
        settings.gemini_model_fast
        if settings.llm_provider == "gemini"
        else settings.anthropic_model_fast
    )
    assert fake.calls[0]["model"] == expected
    assert results[0].category == "outros.diversos"
