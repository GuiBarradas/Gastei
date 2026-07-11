"""``SyncService`` against real SQLAlchemy plus a ``FakeBankConnector``."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy.orm import Session

from gastei.repositories.account_repo import AccountRepository, ItemRepository
from gastei.repositories.transaction_repo import SQLAlchemyTransactionRepository
from gastei.schemas.transaction import (
    AccountDTO,
    ItemDTO,
    TransactionDTO,
)
from gastei.services.sync_service import SyncService
from tests.fakes import FakeBankConnector, FakeClassifier

pytestmark = pytest.mark.integration


def _build_bank_with_data() -> FakeBankConnector:
    item = ItemDTO(
        external_id="item-1",
        connector_id=201,
        institution_name="Itaú",
        status="UPDATED",
        last_synced_at=datetime(2026, 5, 1, 10, 0),
    )
    account = AccountDTO(
        external_id="acc-1",
        item_external_id="item-1",
        type="CHECKING",
        name="CC",
        balance=2500.0,
    )
    txs = [
        TransactionDTO(
            external_id="tx-1",
            account_external_id="acc-1",
            date=date(2026, 4, 15),
            amount=-50.0,
            description="IFOOD *RESTAURANTE",
        ),
        TransactionDTO(
            external_id="tx-2",
            account_external_id="acc-1",
            date=date(2026, 4, 20),
            amount=5000.0,
            description="SALARIO 04/2026",
        ),
    ]
    return FakeBankConnector(
        items=[item],
        accounts_by_item={"item-1": [account]},
        transactions_by_account={"acc-1": txs},
    )


def _make_service(
    db_session: Session,
    bank: FakeBankConnector,
    classifier: FakeClassifier | None = None,
) -> SyncService:
    return SyncService(
        bank=bank,
        tx_repo=SQLAlchemyTransactionRepository(db_session),
        account_repo=AccountRepository(db_session),
        item_repo=ItemRepository(db_session),
        classifier=classifier,
    )


# --------------------------------------------------------------------------------------
# Caminho feliz
# --------------------------------------------------------------------------------------


async def test_sync_persists_items_accounts_and_transactions(
    db_session: Session,
) -> None:
    service = _make_service(db_session, _build_bank_with_data())

    result = await service.sync_all()

    assert result.items_synced == 1
    assert result.accounts_synced == 1
    assert result.transactions_imported == 2
    assert result.transactions_duplicates == 0
    assert result.errors == []

    # Persistido?
    account_repo = AccountRepository(db_session)
    assert {a.id for a in account_repo.list_all()} == {"acc-1"}
    item_repo = ItemRepository(db_session)
    assert {i.id for i in item_repo.list_all()} == {"item-1"}


async def test_sync_is_idempotent(db_session: Session) -> None:
    bank = _build_bank_with_data()
    service = _make_service(db_session, bank)

    first = await service.sync_all()
    second = await service.sync_all()

    assert first.transactions_imported == 2
    assert first.transactions_duplicates == 0
    assert second.transactions_imported == 0
    assert second.transactions_duplicates == 2


async def test_sync_classifies_new_transactions_when_classifier_present(
    db_session: Session,
) -> None:
    bank = _build_bank_with_data()
    classifier = FakeClassifier(
        mapping={"ifood": "alimentacao.delivery", "salario": "renda.salario"},
        source="rule",
    )
    service = _make_service(db_session, bank, classifier=classifier)

    result = await service.sync_all()

    assert result.transactions_categorized == 2
    repo = SQLAlchemyTransactionRepository(db_session)
    txs = await repo.list_by_account("acc-1")
    by_id = {t.id: t for t in txs}
    assert by_id["tx-1"].category == "alimentacao.delivery"
    assert by_id["tx-2"].category == "renda.salario"


async def test_sync_does_not_classify_duplicates(db_session: Session) -> None:
    bank = _build_bank_with_data()
    classifier = FakeClassifier(mapping={"ifood": "alimentacao.delivery"})
    service = _make_service(db_session, bank, classifier=classifier)

    await service.sync_all()
    calls_after_first = len(classifier.calls)

    await service.sync_all()
    # Nenhuma nova → classifier não deveria ser chamado de novo
    assert len(classifier.calls) == calls_after_first


# --------------------------------------------------------------------------------------
# Casos de borda
# --------------------------------------------------------------------------------------


async def test_sync_with_no_items_returns_empty_result(db_session: Session) -> None:
    service = _make_service(db_session, FakeBankConnector())
    result = await service.sync_all()

    assert result.items_synced == 0
    assert result.accounts_synced == 0
    assert result.transactions_imported == 0


async def test_sync_persists_account_balance_correctly(
    db_session: Session,
) -> None:
    bank = _build_bank_with_data()
    await _make_service(db_session, bank).sync_all()

    account = AccountRepository(db_session).list_all()[0]
    assert account.balance == 2500.0
    assert account.name == "CC"
    assert account.type == "CHECKING"
