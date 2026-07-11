"""``GET /transactions`` and ``PATCH /transactions/{id}``."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from gastei.api.deps import (
    get_classifier,
    get_db_session,
    get_example_store,
    get_transaction_repo,
)
from gastei.domain.ports import Classifier, ExampleStore, TransactionRepository
from gastei.models.account import Account as AccountORM
from gastei.schemas.categorization import Example
from gastei.schemas.transaction import Transaction

logger = logging.getLogger(__name__)


def resolve_account_ids(
    session: Session,
    account_id: str | None = None,
    item_id: str | None = None,
) -> list[str]:
    """Shared helper: turn an ``account_id`` / ``item_id`` filter into a list of account ids.

    With neither filter set, returns **every** account — the consolidated view.
    """
    if account_id:
        return [account_id]
    if item_id:
        return list(
            session.scalars(select(AccountORM.id).where(AccountORM.item_id == item_id)).all()
        )
    return list(session.scalars(select(AccountORM.id)).all())


router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionPatch(BaseModel):
    category: str = Field(min_length=1)


@router.get("", response_model=list[Transaction])
async def list_transactions(
    account_id: str | None = Query(None, description="Filter by a specific account"),
    item_id: str | None = Query(None, description="Filter by bank (all of its accounts)"),
    start: date | None = Query(None),
    end: date | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(
        None, description="Case-insensitive substring search on description"
    ),
    limit: int = Query(500, ge=1, le=5000),
    session: Session = Depends(get_db_session),
    repo: TransactionRepository = Depends(get_transaction_repo),
) -> list[Transaction]:
    """No filter = every account. Use ``account_id`` or ``item_id`` to narrow down."""
    account_ids = resolve_account_ids(session, account_id=account_id, item_id=item_id)

    all_txs: list[Transaction] = []
    for aid in account_ids:
        all_txs.extend(await repo.list_by_account(aid, start=start, end=end))

    if category:
        all_txs = [t for t in all_txs if t.category == category]
    if search:
        needle = search.lower()
        all_txs = [t for t in all_txs if needle in t.description.lower()]

    all_txs.sort(key=lambda t: t.date, reverse=True)
    return all_txs[:limit]


@router.patch("/{tx_id}", response_model=dict[str, str])
async def patch_transaction(
    tx_id: str,
    payload: TransactionPatch,
    repo: TransactionRepository = Depends(get_transaction_repo),
    example_store: ExampleStore = Depends(get_example_store),
) -> dict[str, str]:
    """Manually update a transaction's category. ``source='user'``, ``confidence=1.0``.

    Also records the correction as an ``Example`` in the store (feedback loop —
    see ARCHITECTURE.md §2). The next ``LLMClassifier`` invocation uses it as
    a few-shot.
    """
    tx = await repo.get(tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail=f"Transaction not found: {tx_id}")

    try:
        await repo.update_category(
            tx_id=tx_id,
            category=payload.category,
            source="user",
            confidence=1.0,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Transaction not found: {tx_id}") from exc

    example_store.add(
        Example(
            description=tx.description,
            amount=tx.amount,
            category=payload.category,
            source="user_correction",
        )
    )

    return {"status": "ok", "tx_id": tx_id, "category": payload.category}


class RecategorizeResult(BaseModel):
    candidates: int = Field(description="Transactions that were uncategorized or rule-only")
    categorized: int = Field(description="Transactions that received a new category")
    skipped: int = Field(
        description="Transactions the classifier did not produce a valid category for"
    )
    chunks_total: int = 0
    chunks_failed: int = 0
    errors: list[str] = Field(
        default_factory=list, description="First few errors (max 5) for diagnosis"
    )


@router.post("/recategorize", response_model=RecategorizeResult)
async def recategorize_uncategorized(
    limit: int = Query(default=2000, ge=1, le=10000),
    chunk_size: int = Query(
        default=25,
        ge=5,
        le=100,
        description="Number of transactions per LLM call (avoids blowing the context window).",
    ),
    repo: TransactionRepository = Depends(get_transaction_repo),
    classifier: Classifier = Depends(get_classifier),
) -> RecategorizeResult:
    """Run the categorization pipeline over already-imported uncategorized transactions.

    Chunked to keep each LLM call small. Partial errors do not abort the batch.
    """
    candidates = await repo.list_uncategorized(limit=limit)

    if not candidates:
        return RecategorizeResult(
            candidates=0, categorized=0, skipped=0, chunks_total=0, chunks_failed=0
        )

    categorized = 0
    chunks_failed = 0
    errors: list[str] = []
    chunks = [candidates[i : i + chunk_size] for i in range(0, len(candidates), chunk_size)]
    logger.info(
        "Recategorize: %d candidates, %d chunks of %d",
        len(candidates),
        len(chunks),
        chunk_size,
    )

    for idx, chunk in enumerate(chunks, start=1):
        try:
            results = await classifier.classify_batch(chunk, examples=[])
        except Exception as exc:
            chunks_failed += 1
            err = f"chunk {idx}/{len(chunks)}: {type(exc).__name__}: {exc}"
            logger.warning(err)
            if len(errors) < 5:
                errors.append(err)
            continue

        by_id = {r.transaction_id: r for r in results}
        for tx in chunk:
            r = by_id.get(tx.id)
            if r is None:
                continue
            try:
                await repo.update_category(
                    tx_id=r.transaction_id,
                    category=r.category,
                    source=r.source,
                    confidence=r.confidence,
                )
                categorized += 1
            except KeyError:
                continue
        logger.info(
            "Chunk %d/%d: +%d categorized (of %d tx)",
            idx,
            len(chunks),
            len(by_id),
            len(chunk),
        )

    return RecategorizeResult(
        candidates=len(candidates),
        categorized=categorized,
        skipped=len(candidates) - categorized,
        chunks_total=len(chunks),
        chunks_failed=chunks_failed,
        errors=errors,
    )
