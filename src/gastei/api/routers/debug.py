"""Diagnostic endpoints — useful when something is not working as expected.

Disabled defaults would be fine here (mount only in dev). We keep them on
because the app is single-user and the endpoints are read-only or use
synthesized inputs.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gastei.api.deps import (
    _cached_rule_engine,
    get_classifier,
    get_db_session,
    get_llm_client,
)
from gastei.config import get_settings
from gastei.domain.ports import Classifier, LLMClient
from gastei.models.category import Category as CategoryORM
from gastei.models.transaction import Transaction as TransactionORM
from gastei.schemas.transaction import Transaction

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/classifier-status")
def classifier_status(
    session: Session = Depends(get_db_session),
    llm: LLMClient | None = Depends(get_llm_client),
) -> dict:
    """Report the state of the categorization pipeline — a quick health check."""
    settings = get_settings()
    rule_engine = _cached_rule_engine()

    rules_count = len(rule_engine)
    categories_count = session.scalar(select(func.count(CategoryORM.code))) or 0
    uncategorized_count = (
        session.scalar(
            select(func.count(TransactionORM.id)).where(TransactionORM.category.is_(None))
        )
        or 0
    )
    total_tx = session.scalar(select(func.count(TransactionORM.id))) or 0

    if settings.llm_provider == "gemini":
        model_fast, model_smart = settings.gemini_model_fast, settings.gemini_model_smart
    else:
        model_fast, model_smart = settings.anthropic_model_fast, settings.anthropic_model_smart

    return {
        "llm_provider": settings.llm_provider,
        "llm_configured": llm is not None,
        "llm_class": type(llm).__name__ if llm else None,
        "model_fast": model_fast,
        "model_smart": model_smart,
        "rules_loaded": rules_count,
        "categories_in_db": categories_count,
        "transactions_total": total_tx,
        "transactions_uncategorized": uncategorized_count,
    }


@router.post("/classify-sample")
async def classify_sample(
    description: str,
    amount: float = -50.0,
    classifier: Classifier = Depends(get_classifier),
) -> dict:
    """Classify a single synthetic transaction and return the result.

    Useful to verify the pipeline works end-to-end without touching the database.
    """
    if not description.strip():
        raise HTTPException(status_code=400, detail="description is empty")

    fake_tx = Transaction(
        id="debug-tx",
        account_id="debug-acc",
        date=date.today(),
        amount=amount,
        description=description,
    )
    try:
        results = await classifier.classify_batch([fake_tx], examples=[])
    except Exception as exc:
        return {
            "ok": False,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "results": [],
        }

    return {
        "ok": True,
        "input": {"description": description, "amount": amount},
        "results": [r.model_dump() for r in results],
    }
