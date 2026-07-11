"""``SQLAlchemyExampleStore`` against a real database."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from gastei.domain.ports import ExampleStore
from gastei.repositories.example_repo import SQLAlchemyExampleStore
from gastei.schemas.categorization import Example

pytestmark = pytest.mark.integration


def _ex(description: str, category: str = "outros.diversos") -> Example:
    return Example(
        description=description,
        category=category,
        source="user_correction",
    )


def test_satisfies_port(db_session: Session) -> None:
    assert isinstance(SQLAlchemyExampleStore(db_session), ExampleStore)


def test_add_then_most_relevant_returns_it(db_session: Session) -> None:
    store = SQLAlchemyExampleStore(db_session)
    store.add(_ex("STARBUCKS BR"))

    result = store.most_relevant(txs=[], k=10)
    assert len(result) == 1
    assert result[0].description == "STARBUCKS BR"


def test_most_relevant_orders_recent_first(db_session: Session) -> None:
    store = SQLAlchemyExampleStore(db_session)
    for i in range(5):
        store.add(_ex(f"desc{i}"))

    result = store.most_relevant(txs=[], k=3)
    assert [e.description for e in result] == ["desc4", "desc3", "desc2"]


def test_most_relevant_respects_k(db_session: Session) -> None:
    store = SQLAlchemyExampleStore(db_session)
    for i in range(10):
        store.add(_ex(f"d{i}"))

    assert len(store.most_relevant(txs=[], k=4)) == 4


def test_empty_store_returns_empty(db_session: Session) -> None:
    store = SQLAlchemyExampleStore(db_session)
    assert store.most_relevant(txs=[], k=10) == []


def test_add_persists_amount_and_source(db_session: Session) -> None:
    store = SQLAlchemyExampleStore(db_session)
    store.add(
        Example(
            description="X",
            amount=-99.50,
            category="alimentacao.delivery",
            source="manual_seed",
        )
    )
    result = store.most_relevant(txs=[], k=10)
    assert result[0].amount == -99.50
    assert result[0].source == "manual_seed"
    assert result[0].category == "alimentacao.delivery"
