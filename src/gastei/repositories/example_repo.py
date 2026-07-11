"""SQLAlchemyExampleStore — adapter implementing the ``ExampleStore`` port.

Realizes the feedback loop principle (ARCHITECTURE.md §2): user corrections
become few-shot examples for the next LLM batch. Current ranking strategy
mirrors ``FakeExampleStore`` — return the K most recent examples.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from gastei.models.example import Example as ExampleORM
from gastei.schemas.categorization import Example
from gastei.schemas.transaction import Transaction


class SQLAlchemyExampleStore:
    """Implements ``gastei.domain.ports.ExampleStore``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def most_relevant(self, txs: list[Transaction], k: int = 20) -> list[Example]:
        # Current strategy: top-K most recent (``txs`` ignored).
        # Future iteration: embed the descriptions and rank by cosine similarity.
        _ = txs
        rows = self._session.scalars(
            select(ExampleORM).order_by(ExampleORM.created_at.desc()).limit(k)
        ).all()
        return [
            Example(
                description=r.description,
                amount=r.amount,
                category=r.category,
                source=r.source,  # type: ignore[arg-type]
            )
            for r in rows
        ]

    def add(self, example: Example) -> None:
        self._session.add(
            ExampleORM(
                description=example.description,
                amount=example.amount,
                category=example.category,
                source=example.source,
            )
        )
        self._session.commit()
