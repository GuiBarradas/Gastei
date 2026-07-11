"""Guarantees that every Fake implements its matching port.

``runtime_checkable`` Protocols only verify method presence (not
signatures). Even so, these tests catch the most common failure mode:
"I added a method to the port and forgot to update the fake".
"""

from __future__ import annotations

from datetime import date

import pytest

from gastei.domain.ports import (
    BankConnector,
    Classifier,
    ExampleStore,
    LLMClient,
    TransactionRepository,
)
from gastei.schemas.categorization import Example
from gastei.schemas.llm import LLMResponse
from gastei.schemas.transaction import (
    AccountDTO,
    ItemDTO,
    Transaction,
    TransactionDTO,
)
from tests.fakes import (
    FakeBankConnector,
    FakeClassifier,
    FakeExampleStore,
    FakeLLMClient,
    FakeTransactionRepository,
)

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------------------
# Conformidade estrutural: cada fake responde isinstance() do seu port
# --------------------------------------------------------------------------------------


def test_fake_transaction_repository_satisfies_port() -> None:
    assert isinstance(FakeTransactionRepository(), TransactionRepository)


def test_fake_example_store_satisfies_port() -> None:
    assert isinstance(FakeExampleStore(), ExampleStore)


def test_fake_classifier_satisfies_port() -> None:
    assert isinstance(FakeClassifier(), Classifier)


def test_fake_llm_client_satisfies_port() -> None:
    assert isinstance(FakeLLMClient(), LLMClient)


def test_fake_bank_connector_satisfies_port() -> None:
    assert isinstance(FakeBankConnector(), BankConnector)


# --------------------------------------------------------------------------------------
# Conformidade funcional: comportamento mínimo correto pra que sirvam em TDD
# --------------------------------------------------------------------------------------


def _make_tx(tx_id: str = "t1", account: str = "a1", category: str | None = None) -> Transaction:
    return Transaction(
        id=tx_id,
        account_id=account,
        date=date(2026, 5, 1),
        amount=-50.0,
        description="iFood pedido",
        category=category,
    )


async def test_repository_upsert_returns_inserted_then_updated_counts() -> None:
    repo = FakeTransactionRepository()
    inserted, updated = await repo.upsert_many([_make_tx("a"), _make_tx("b")])
    assert (inserted, updated) == (2, 0)

    inserted2, updated2 = await repo.upsert_many([_make_tx("a"), _make_tx("c")])
    assert (inserted2, updated2) == (1, 1)


async def test_repository_list_uncategorized_filters() -> None:
    repo = FakeTransactionRepository(
        seed=[
            _make_tx("a", category=None),
            _make_tx("b", category="alimentacao.delivery"),
            _make_tx("c", category=None),
        ]
    )
    uncategorized = await repo.list_uncategorized()
    assert {t.id for t in uncategorized} == {"a", "c"}


async def test_repository_update_category_records_call_and_mutates() -> None:
    repo = FakeTransactionRepository(seed=[_make_tx("a")])
    await repo.update_category("a", "alimentacao.delivery", "rule", 1.0)

    assert repo.update_category_calls == [("a", "alimentacao.delivery", "rule", 1.0)]
    updated = repo.get_sync("a")
    assert updated is not None
    assert updated.category == "alimentacao.delivery"
    assert updated.category_source == "rule"
    assert updated.category_confidence == 1.0


def test_example_store_returns_most_recent_first() -> None:
    store = FakeExampleStore()
    for i in range(5):
        store.add(
            Example(description=f"desc{i}", category="outros.diversos", source="user_correction")
        )

    top = store.most_relevant(txs=[], k=3)
    assert [e.description for e in top] == ["desc4", "desc3", "desc2"]


async def test_classifier_uses_substring_mapping() -> None:
    clf = FakeClassifier(mapping={"ifood": "alimentacao.delivery", "uber": "transporte.app"})
    results = await clf.classify_batch(
        txs=[_make_tx("a"), _make_tx("b")],
        examples=[],
    )
    assert results[0].category == "alimentacao.delivery"
    assert results[0].source == "llm"
    assert results[1].category == "alimentacao.delivery"


async def test_classifier_falls_back_to_default() -> None:
    clf = FakeClassifier(default_category="outros.diversos")
    tx = Transaction(
        id="x",
        account_id="a",
        date=date(2026, 5, 1),
        amount=-10.0,
        description="algo desconhecido",
    )
    results = await clf.classify_batch(txs=[tx], examples=[])
    assert results[0].category == "outros.diversos"


async def test_llm_client_pops_responses_in_order() -> None:
    r1 = LLMResponse(stop_reason="tool_use", text="")
    r2 = LLMResponse(stop_reason="end_turn", text="pronto")
    llm = FakeLLMClient(responses=[r1, r2])

    a = await llm.messages_create(model="m", system="s", messages=[])
    b = await llm.messages_create(model="m", system="s", messages=[])

    assert a is r1
    assert b is r2
    assert len(llm.calls) == 2
    assert llm.calls[0]["model"] == "m"


async def test_llm_client_raises_when_queue_empty() -> None:
    llm = FakeLLMClient()
    with pytest.raises(AssertionError, match="no queued responses"):
        await llm.messages_create(model="m", system="s", messages=[])


async def test_bank_connector_seeds_and_filters_by_date() -> None:
    item = ItemDTO(
        external_id="i1",
        connector_id=201,
        institution_name="Itaú",
        status="UPDATED",
    )
    account = AccountDTO(
        external_id="a1",
        item_external_id="i1",
        type="CHECKING",
        name="CC",
        balance=1000.0,
    )
    txs = [
        TransactionDTO(
            external_id="t1",
            account_external_id="a1",
            date=date(2026, 4, 1),
            amount=-20.0,
            description="x",
        ),
        TransactionDTO(
            external_id="t2",
            account_external_id="a1",
            date=date(2026, 5, 1),
            amount=-30.0,
            description="y",
        ),
    ]
    bank = FakeBankConnector(
        items=[item],
        accounts_by_item={"i1": [account]},
        transactions_by_account={"a1": txs},
    )

    assert [i.external_id for i in await bank.list_items()] == ["i1"]
    assert [a.external_id for a in await bank.list_accounts("i1")] == ["a1"]

    filtered = await bank.list_transactions("a1", date_from=date(2026, 4, 15), date_to=None)
    assert [t.external_id for t in filtered] == ["t2"]

    await bank.trigger_sync("i1")
    assert bank.triggered_syncs == ["i1"]
