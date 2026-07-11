"""End-to-end integration of the ``POST /imports/ofx`` endpoint.

Full pipeline: HTTP → router → service → ``SQLAlchemyTransactionRepository`` → DB.
Overrides ``get_db_session`` to point at the conftest test database.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from gastei.api.deps import get_db_session
from gastei.api.main import create_app
from gastei.models.account import Account as AccountORM
from gastei.models.item import Item as ItemORM

pytestmark = pytest.mark.integration


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
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


@pytest.fixture
def seeded_account(db_session: Session) -> str:
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


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app = create_app()

    def _override_db() -> Iterator[Session]:
        yield db_session  # não fechar — fixture cuida

    app.dependency_overrides[get_db_session] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health_endpoint(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_post_ofx_returns_201_and_persists(client: TestClient, seeded_account: str) -> None:
    response = client.post(
        "/imports/ofx",
        data={"account_id": seeded_account},
        files={"file": ("test.ofx", SAMPLE_OFX, "application/x-ofx")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body == {"imported": 2, "duplicates": 0, "errors": []}


def test_post_ofx_is_idempotent(client: TestClient, seeded_account: str) -> None:
    payload = {
        "data": {"account_id": seeded_account},
        "files": {"file": ("test.ofx", SAMPLE_OFX, "application/x-ofx")},
    }
    first = client.post("/imports/ofx", **payload).json()
    second = client.post("/imports/ofx", **payload).json()

    assert first["imported"] == 2 and first["duplicates"] == 0
    assert second["imported"] == 0 and second["duplicates"] == 2


def test_post_ofx_rejects_empty_file(client: TestClient, seeded_account: str) -> None:
    r = client.post(
        "/imports/ofx",
        data={"account_id": seeded_account},
        files={"file": ("empty.ofx", b"", "application/x-ofx")},
    )
    assert r.status_code == 400


def test_post_ofx_rejects_malformed(client: TestClient, seeded_account: str) -> None:
    r = client.post(
        "/imports/ofx",
        data={"account_id": seeded_account},
        files={"file": ("bad.ofx", b"isto nao eh ofx", "application/x-ofx")},
    )
    assert r.status_code == 422


def test_post_ofx_auto_resolves_when_account_id_omitted(client: TestClient, db_session) -> None:
    """Sem account_id → service inspeciona OFX e cria Item+Account auto."""
    from gastei.models.account import Account
    from gastei.models.item import Item

    # SAMPLE_OFX desta integração tem BANKID=001 e ACCTID=12345
    r = client.post(
        "/imports/ofx",
        files={"file": ("t.ofx", SAMPLE_OFX, "application/x-ofx")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["imported"] == 2

    items = db_session.query(Item).all()
    assert any(i.id == "ofx-001" for i in items)
    accounts = db_session.query(Account).all()
    assert any(a.number == "12345" for a in accounts)


def test_post_ofx_inspect_returns_fingerprint(client: TestClient) -> None:
    r = client.post(
        "/imports/ofx/inspect",
        files={"file": ("t.ofx", SAMPLE_OFX, "application/x-ofx")},
    )
    assert r.status_code == 200
    fp = r.json()
    assert fp["bank_id"] == "001"
    assert fp["bank_name"] == "Banco do Brasil"
    assert fp["account_id"] == "12345"
    assert fp["transaction_count"] == 2
