"""Integration tests for the read endpoints (accounts, items, transactions, insights)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from datetime import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from gastei.api.deps import get_db_session
from gastei.api.main import create_app
from gastei.models.account import Account as AccountORM
from gastei.models.item import Item as ItemORM
from gastei.models.transaction import Transaction as TransactionORM

pytestmark = pytest.mark.integration


@pytest.fixture
def seeded_db(db_session: Session) -> str:
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
        name="Conta Corrente",
        balance=2500.0,
        updated_at=dt(2026, 5, 1),
    )
    txs = [
        TransactionORM(
            id="t1",
            account_id="acc-1",
            date=date(2026, 4, 5),
            amount=-50.0,
            description="IFOOD",
            category="alimentacao.delivery",
        ),
        TransactionORM(
            id="t2",
            account_id="acc-1",
            date=date(2026, 4, 10),
            amount=-30.0,
            description="UBER",
            category="transporte.app",
        ),
        TransactionORM(
            id="t3",
            account_id="acc-1",
            date=date(2026, 4, 20),
            amount=5000.0,
            description="SALARIO",
            category="renda.salario",
        ),
        TransactionORM(
            id="t4",
            account_id="acc-1",
            date=date(2026, 4, 25),
            amount=-100.0,
            description="NETFLIX",
            category=None,
        ),
    ]
    db_session.add_all([item, account, *txs])
    db_session.commit()
    return "acc-1"


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app = create_app()

    def _override_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------- Accounts / Items ----------------


def test_list_accounts(client: TestClient, seeded_db: str) -> None:
    r = client.get("/accounts")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == "acc-1"
    assert body[0]["balance"] == 2500.0


def test_list_items(client: TestClient, seeded_db: str) -> None:
    r = client.get("/items")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["institution_name"] == "Itaú"


# ---------------- Transactions GET / PATCH ----------------


def test_list_transactions_no_filter_returns_all_accounts(
    client: TestClient, seeded_db: str
) -> None:
    """Sem account_id nem item_id → retorna tx de todas as contas (visão consolidada)."""
    r = client.get("/transactions")
    assert r.status_code == 200
    # seeded_db cria 1 account com 4 tx — retorno deve incluir todas
    assert len(r.json()) == 4


def test_list_transactions_filters_by_item_id(client: TestClient, seeded_db: str) -> None:
    """item_id (banco) expande pra todas as accounts daquele item."""
    r = client.get("/transactions", params={"item_id": "item-1"})
    assert r.status_code == 200
    assert len(r.json()) == 4


def test_list_transactions_returns_all_for_account(client: TestClient, seeded_db: str) -> None:
    r = client.get("/transactions", params={"account_id": seeded_db})
    assert r.status_code == 200
    assert len(r.json()) == 4


def test_list_transactions_filters_by_category(client: TestClient, seeded_db: str) -> None:
    r = client.get(
        "/transactions",
        params={"account_id": seeded_db, "category": "transporte.app"},
    )
    body = r.json()
    assert {t["id"] for t in body} == {"t2"}


def test_list_transactions_filters_by_search(client: TestClient, seeded_db: str) -> None:
    r = client.get(
        "/transactions",
        params={"account_id": seeded_db, "search": "netflix"},
    )
    assert {t["id"] for t in r.json()} == {"t4"}


def test_list_transactions_filters_by_date_range(client: TestClient, seeded_db: str) -> None:
    r = client.get(
        "/transactions",
        params={"account_id": seeded_db, "start": "2026-04-15", "end": "2026-04-30"},
    )
    assert {t["id"] for t in r.json()} == {"t3", "t4"}


def test_patch_transaction_updates_category(client: TestClient, seeded_db: str) -> None:
    r = client.patch("/transactions/t4", json={"category": "lazer.streaming"})
    assert r.status_code == 200
    assert r.json()["category"] == "lazer.streaming"

    follow = client.get(
        "/transactions",
        params={"account_id": seeded_db, "category": "lazer.streaming"},
    )
    assert {t["id"] for t in follow.json()} == {"t4"}


def test_patch_transaction_creates_example_for_feedback_loop(
    client: TestClient, seeded_db: str, db_session
) -> None:
    """§2.5 — correção do usuário vira few-shot pra próxima rodada do LLM."""
    from gastei.models.example import Example

    client.patch("/transactions/t4", json={"category": "lazer.streaming"})

    examples = db_session.query(Example).all()
    assert len(examples) == 1
    ex = examples[0]
    assert ex.description == "NETFLIX"  # description original da tx t4
    assert ex.category == "lazer.streaming"
    assert ex.source == "user_correction"
    assert ex.amount == -100.0


def test_patch_transaction_404_on_missing(client: TestClient, seeded_db: str) -> None:
    r = client.patch("/transactions/nope", json={"category": "outros.diversos"})
    assert r.status_code == 404


# ---------------- Insights ----------------


def test_spending_by_category(client: TestClient, seeded_db: str) -> None:
    r = client.get("/insights/spending-by-category", params={"account_id": seeded_db})
    assert r.status_code == 200
    body = r.json()
    cats = {item["category"]: item["amount"] for item in body}
    assert cats["alimentacao.delivery"] == 50.0
    assert cats["transporte.app"] == 30.0
    assert cats["sem_categoria"] == 100.0


def test_monthly_summary(client: TestClient, seeded_db: str) -> None:
    r = client.get("/insights/monthly-summary", params={"account_id": seeded_db})
    body = r.json()
    assert len(body) == 1
    apr = body[0]
    assert apr["year"] == 2026
    assert apr["month"] == 4
    assert apr["income"] == 5000.0
    assert apr["expense"] == 180.0
    assert apr["net"] == 4820.0


def test_top_merchants(client: TestClient, seeded_db: str) -> None:
    r = client.get(
        "/insights/top-merchants",
        params={"account_id": seeded_db, "limit": 5},
    )
    body = r.json()
    by_m = {m["merchant"]: m["amount"] for m in body}
    assert by_m["NETFLIX"] == 100.0
    assert by_m["IFOOD"] == 50.0
    assert by_m["UBER"] == 30.0
    assert "SALARIO" not in by_m  # receita não conta como merchant
