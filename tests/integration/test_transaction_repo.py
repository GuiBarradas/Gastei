"""Integration: ``SQLAlchemyTransactionRepository`` against real SQLite.

Reuses the ``db_session`` fixture from ``conftest`` (temporary database
with migrations applied).
"""

from __future__ import annotations

from datetime import date
from datetime import datetime as dt

import pytest
from sqlalchemy.orm import Session

from gastei.models.account import Account as AccountORM
from gastei.models.item import Item as ItemORM
from gastei.repositories.transaction_repo import SQLAlchemyTransactionRepository
from gastei.schemas.transaction import Transaction

pytestmark = pytest.mark.integration


@pytest.fixture
def seeded_account(db_session: Session) -> str:
    """Cria item + account pra satisfazer FKs. Retorna account_id."""
    item = ItemORM(
        id="item-1",
        connector_id=201,
        institution_name="Itaú",
        status="UPDATED",
    )
    account = AccountORM(
        id="acc-1",
        item_id="item-1",
        type="CHECKING",
        name="CC",
        balance=1000.0,
        updated_at=dt(2026, 5, 1, 0, 0, 0),
    )
    db_session.add_all([item, account])
    db_session.commit()
    return "acc-1"


def _tx(tx_id: str, account_id: str, *, category: str | None = None) -> Transaction:
    return Transaction(
        id=tx_id,
        account_id=account_id,
        date=date(2026, 5, 1),
        amount=-50.0,
        description="iFood pedido",
        category=category,
    )


async def test_upsert_inserts_then_updates(db_session: Session, seeded_account: str) -> None:
    repo = SQLAlchemyTransactionRepository(db_session)

    inserted, updated = await repo.upsert_many([_tx("a", seeded_account), _tx("b", seeded_account)])
    assert (inserted, updated) == (2, 0)

    inserted2, updated2 = await repo.upsert_many(
        [_tx("a", seeded_account), _tx("c", seeded_account)]
    )
    assert (inserted2, updated2) == (1, 1)


async def test_list_by_account_orders_desc_by_date(
    db_session: Session, seeded_account: str
) -> None:
    repo = SQLAlchemyTransactionRepository(db_session)
    older = Transaction(
        id="x",
        account_id=seeded_account,
        date=date(2026, 4, 10),
        amount=-10.0,
        description="velho",
    )
    newer = Transaction(
        id="y",
        account_id=seeded_account,
        date=date(2026, 5, 10),
        amount=-20.0,
        description="novo",
    )
    await repo.upsert_many([older, newer])

    rows = await repo.list_by_account(seeded_account)
    assert [r.id for r in rows] == ["y", "x"]


async def test_list_by_account_filters_by_date_range(
    db_session: Session, seeded_account: str
) -> None:
    repo = SQLAlchemyTransactionRepository(db_session)
    txs = [
        Transaction(
            id=str(i),
            account_id=seeded_account,
            date=date(2026, 4, i),
            amount=-1.0,
            description=f"d{i}",
        )
        for i in (1, 15, 28)
    ]
    await repo.upsert_many(txs)

    rows = await repo.list_by_account(
        seeded_account, start=date(2026, 4, 10), end=date(2026, 4, 20)
    )
    assert [r.id for r in rows] == ["15"]


async def test_list_uncategorized_filters_null_category(
    db_session: Session, seeded_account: str
) -> None:
    repo = SQLAlchemyTransactionRepository(db_session)
    await repo.upsert_many(
        [
            _tx("a", seeded_account, category=None),
            _tx("b", seeded_account, category="alimentacao.delivery"),
            _tx("c", seeded_account, category=None),
        ]
    )

    rows = await repo.list_uncategorized()
    assert {r.id for r in rows} == {"a", "c"}


async def test_update_category_persists(db_session: Session, seeded_account: str) -> None:
    repo = SQLAlchemyTransactionRepository(db_session)
    await repo.upsert_many([_tx("a", seeded_account)])

    await repo.update_category("a", "alimentacao.delivery", "rule", 1.0)

    rows = await repo.list_by_account(seeded_account)
    assert rows[0].category == "alimentacao.delivery"
    assert rows[0].category_source == "rule"
    assert rows[0].category_confidence == 1.0


async def test_update_category_raises_on_missing(db_session: Session, seeded_account: str) -> None:
    repo = SQLAlchemyTransactionRepository(db_session)
    with pytest.raises(KeyError):
        await repo.update_category("nope", "outros.diversos", "user", None)
