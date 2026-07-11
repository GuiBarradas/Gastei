"""OFXImportService specs — TDD (ARCHITECTURE.md §7.4).

Coverage:

- Deterministic hashing (same file + account_id twice → 0 new, N duplicates).
- Changing ``account_id`` changes the hash (same transactions in a different
  account count as new).
- Signs are preserved (debits negative, credits positive).
- ``datetime`` → ``date`` conversion.
- Description: prefers ``payee`` / ``name``; falls back to ``memo``.
- Optional ``Classifier``: called when present, not called when ``None``.
- ``ImportResult`` is populated correctly.
"""

from __future__ import annotations

import pytest

from gastei.services.ofx_import_service import OFXImportService
from tests.fakes import FakeClassifier, FakeTransactionRepository

pytestmark = pytest.mark.unit


SAMPLE_OFX = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS><DTSERVER>20260501000000</DTSERVER><LANGUAGE>POR</LANGUAGE></SONRS></SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1</TRNUID>
<STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>
<STMTRS>
<CURDEF>BRL</CURDEF>
<BANKACCTFROM><BANKID>001</BANKID><ACCTID>12345</ACCTID><ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260401000000</DTSTART>
<DTEND>20260430000000</DTEND>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260415120000</DTPOSTED><TRNAMT>-50.00</TRNAMT><FITID>FIT001</FITID><MEMO>IFOOD *RESTAURANTE</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>CREDIT</TRNTYPE><DTPOSTED>20260420120000</DTPOSTED><TRNAMT>5000.00</TRNAMT><FITID>FIT002</FITID><MEMO>SALARIO COMP 04/2026</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260422120000</DTPOSTED><TRNAMT>-25.50</TRNAMT><FITID>FIT003</FITID><NAME>UBER TRIP</NAME><MEMO>Corrida Uber app</MEMO></STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""

EMPTY_OFX = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS><DTSERVER>20260501000000</DTSERVER><LANGUAGE>POR</LANGUAGE></SONRS></SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1</TRNUID>
<STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>
<STMTRS>
<CURDEF>BRL</CURDEF>
<BANKACCTFROM><BANKID>001</BANKID><ACCTID>12345</ACCTID><ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260401000000</DTSTART>
<DTEND>20260430000000</DTEND>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


# --------------------------------------------------------------------------------------
# Caminho feliz
# --------------------------------------------------------------------------------------


async def test_import_returns_count_of_inserted() -> None:
    repo = FakeTransactionRepository()
    service = OFXImportService(repo=repo)

    result = await service.import_bytes(SAMPLE_OFX, account_id="acc-1")

    assert result.imported == 3
    assert result.duplicates == 0
    assert result.errors == []


async def test_import_persists_via_repository() -> None:
    repo = FakeTransactionRepository()
    service = OFXImportService(repo=repo)

    await service.import_bytes(SAMPLE_OFX, account_id="acc-1")

    persisted = repo.all()
    assert len(persisted) == 3
    assert all(tx.account_id == "acc-1" for tx in persisted)


async def test_amounts_signed_preserved() -> None:
    repo = FakeTransactionRepository()
    service = OFXImportService(repo=repo)

    await service.import_bytes(SAMPLE_OFX, account_id="acc-1")

    amounts = sorted(tx.amount for tx in repo.all())
    assert amounts == [-50.0, -25.5, 5000.0]


async def test_date_converted_to_date_type() -> None:
    from datetime import date as date_t

    repo = FakeTransactionRepository()
    service = OFXImportService(repo=repo)

    await service.import_bytes(SAMPLE_OFX, account_id="acc-1")

    dates = {tx.date for tx in repo.all()}
    assert all(isinstance(d, date_t) for d in dates)
    assert date_t(2026, 4, 15) in dates


async def test_description_prefers_payee_over_memo() -> None:
    repo = FakeTransactionRepository()
    service = OFXImportService(repo=repo)

    await service.import_bytes(SAMPLE_OFX, account_id="acc-1")

    by_amount = {tx.amount: tx for tx in repo.all()}
    uber_tx = by_amount[-25.5]
    # FIT003 tem NAME=UBER TRIP e MEMO=Corrida Uber app — payee/name vence
    assert uber_tx.description == "UBER TRIP"
    assert uber_tx.description_raw == "Corrida Uber app"


async def test_description_falls_back_to_memo_when_no_payee() -> None:
    repo = FakeTransactionRepository()
    service = OFXImportService(repo=repo)

    await service.import_bytes(SAMPLE_OFX, account_id="acc-1")

    by_amount = {tx.amount: tx for tx in repo.all()}
    ifood_tx = by_amount[-50.0]
    assert ifood_tx.description == "IFOOD *RESTAURANTE"


# --------------------------------------------------------------------------------------
# Idempotência (hash determinístico)
# --------------------------------------------------------------------------------------


async def test_reimport_same_file_yields_zero_imported_and_n_duplicates() -> None:
    repo = FakeTransactionRepository()
    service = OFXImportService(repo=repo)

    first = await service.import_bytes(SAMPLE_OFX, account_id="acc-1")
    second = await service.import_bytes(SAMPLE_OFX, account_id="acc-1")

    assert first.imported == 3 and first.duplicates == 0
    assert second.imported == 0 and second.duplicates == 3
    assert len(repo.all()) == 3, "Nenhuma transação adicional persistida"


async def test_changing_account_id_changes_ids() -> None:
    repo = FakeTransactionRepository()
    service = OFXImportService(repo=repo)

    await service.import_bytes(SAMPLE_OFX, account_id="acc-1")
    second = await service.import_bytes(SAMPLE_OFX, account_id="acc-2")

    # Mesmas tx em conta diferente devem ser tratadas como novas
    assert second.imported == 3 and second.duplicates == 0
    assert len(repo.all()) == 6


async def test_ids_are_stable_across_imports() -> None:
    repo1 = FakeTransactionRepository()
    repo2 = FakeTransactionRepository()
    service1 = OFXImportService(repo=repo1)
    service2 = OFXImportService(repo=repo2)

    await service1.import_bytes(SAMPLE_OFX, account_id="acc-1")
    await service2.import_bytes(SAMPLE_OFX, account_id="acc-1")

    ids1 = sorted(tx.id for tx in repo1.all())
    ids2 = sorted(tx.id for tx in repo2.all())
    assert ids1 == ids2, "IDs determinísticos: mesma entrada → mesmo id"


# --------------------------------------------------------------------------------------
# Classifier opcional
# --------------------------------------------------------------------------------------


async def test_classifier_called_when_provided() -> None:
    repo = FakeTransactionRepository()
    classifier = FakeClassifier(
        mapping={"ifood": "alimentacao.delivery"},
        source="rule",
    )
    service = OFXImportService(repo=repo, classifier=classifier)

    await service.import_bytes(SAMPLE_OFX, account_id="acc-1")

    assert len(classifier.calls) >= 1
    classified_txs = classifier.calls[0][0]
    assert {tx.account_id for tx in classified_txs} == {"acc-1"}

    # Categoria foi aplicada via update_category
    by_desc = {tx.description: tx for tx in repo.all()}
    assert by_desc["IFOOD *RESTAURANTE"].category == "alimentacao.delivery"
    assert by_desc["IFOOD *RESTAURANTE"].category_source == "rule"


async def test_classifier_not_called_when_none() -> None:
    repo = FakeTransactionRepository()
    service = OFXImportService(repo=repo, classifier=None)

    await service.import_bytes(SAMPLE_OFX, account_id="acc-1")

    assert all(tx.category is None for tx in repo.all())


async def test_reimport_does_not_re_classify_existing() -> None:
    """Idempotência também na categorização: tx duplicada não re-classifica."""
    repo = FakeTransactionRepository()
    classifier = FakeClassifier(mapping={"ifood": "alimentacao.delivery"})
    service = OFXImportService(repo=repo, classifier=classifier)

    await service.import_bytes(SAMPLE_OFX, account_id="acc-1")
    calls_after_first = len(classifier.calls)

    await service.import_bytes(SAMPLE_OFX, account_id="acc-1")

    # Segunda importação não classificou de novo (todas eram duplicadas)
    assert len(classifier.calls) == calls_after_first


# --------------------------------------------------------------------------------------
# Casos de borda
# --------------------------------------------------------------------------------------


async def test_empty_ofx_returns_zero_imported() -> None:
    repo = FakeTransactionRepository()
    service = OFXImportService(repo=repo)

    result = await service.import_bytes(EMPTY_OFX, account_id="acc-1")

    assert result.imported == 0
    assert result.duplicates == 0
    assert repo.all() == []


async def test_malformed_ofx_raises_value_error() -> None:
    repo = FakeTransactionRepository()
    service = OFXImportService(repo=repo)

    with pytest.raises(ValueError):
        await service.import_bytes(b"isto nao e ofx", account_id="acc-1")


# --------------------------------------------------------------------------------------
# Auto-resolve account from OFX fingerprint (bank_id + account_id)
# --------------------------------------------------------------------------------------

OFX_NUBANK = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS><DTSERVER>20260501000000</DTSERVER><LANGUAGE>POR</LANGUAGE></SONRS></SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1</TRNUID>
<STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>
<STMTRS>
<CURDEF>BRL</CURDEF>
<BANKACCTFROM><BANKID>260</BANKID><ACCTID>12345-6</ACCTID><ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260401000000</DTSTART>
<DTEND>20260430000000</DTEND>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260415120000</DTPOSTED><TRNAMT>-50.00</TRNAMT><FITID>F1</FITID><MEMO>iFood</MEMO></STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


async def test_auto_resolve_requires_repos_or_raises() -> None:
    repo = FakeTransactionRepository()
    service = OFXImportService(repo=repo)  # no item_repo / account_repo wired in

    with pytest.raises(ValueError, match="auto-resolve unavailable"):
        await service.import_bytes(OFX_NUBANK)


@pytest.mark.integration
async def test_auto_resolve_creates_item_and_account_on_first_import(
    db_session,
) -> None:
    from gastei.repositories.account_repo import AccountRepository, ItemRepository
    from gastei.repositories.transaction_repo import SQLAlchemyTransactionRepository

    repo = SQLAlchemyTransactionRepository(db_session)
    item_repo = ItemRepository(db_session)
    account_repo = AccountRepository(db_session)
    service = OFXImportService(repo=repo, item_repo=item_repo, account_repo=account_repo)

    result = await service.import_bytes(OFX_NUBANK)

    assert result.imported == 1

    items = item_repo.list_all()
    assert len(items) == 1
    assert items[0].id == "ofx-260"
    assert items[0].institution_name == "Nubank"

    accounts = account_repo.list_all()
    assert len(accounts) == 1
    assert accounts[0].name == "Nubank Conta"
    assert accounts[0].number == "12345-6"
    assert accounts[0].type == "CHECKING"


@pytest.mark.integration
async def test_auto_resolve_reuses_existing_account_on_second_import(
    db_session,
) -> None:
    from gastei.repositories.account_repo import AccountRepository, ItemRepository
    from gastei.repositories.transaction_repo import SQLAlchemyTransactionRepository

    repo = SQLAlchemyTransactionRepository(db_session)
    item_repo = ItemRepository(db_session)
    account_repo = AccountRepository(db_session)
    service = OFXImportService(repo=repo, item_repo=item_repo, account_repo=account_repo)

    await service.import_bytes(OFX_NUBANK)
    await service.import_bytes(OFX_NUBANK)

    assert len(item_repo.list_all()) == 1
    assert len(account_repo.list_all()) == 1
