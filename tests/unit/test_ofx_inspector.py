"""Specs for the OFX inspector — TDD."""

from __future__ import annotations

from datetime import date

import pytest

from gastei.utils.bank_codes import name_for_bank_code
from gastei.utils.ofx_inspector import inspect_ofx

pytestmark = pytest.mark.unit


def _ofx_bank(bank_id: str = "260", account_id: str = "12345-6") -> bytes:
    return f"""OFXHEADER:100
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
<BANKACCTFROM><BANKID>{bank_id}</BANKID><ACCTID>{account_id}</ACCTID><ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260401000000</DTSTART>
<DTEND>20260430000000</DTEND>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260415120000</DTPOSTED><TRNAMT>-50.00</TRNAMT><FITID>F1</FITID><MEMO>X</MEMO></STMTTRN>
<STMTTRN><TRNTYPE>CREDIT</TRNTYPE><DTPOSTED>20260420120000</DTPOSTED><TRNAMT>1000.00</TRNAMT><FITID>F2</FITID><MEMO>Y</MEMO></STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
""".encode()


def _ofx_credit_card(bank_id: str = "260", card_id: str = "5555444433332222") -> bytes:
    return f"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS><DTSERVER>20260501000000</DTSERVER><LANGUAGE>POR</LANGUAGE><FI><ORG>Nubank</ORG><FID>{bank_id}</FID></FI></SONRS></SIGNONMSGSRSV1>
<CREDITCARDMSGSRSV1>
<CCSTMTTRNRS>
<TRNUID>1</TRNUID>
<STATUS><CODE>0</CODE><SEVERITY>INFO</SEVERITY></STATUS>
<CCSTMTRS>
<CURDEF>BRL</CURDEF>
<CCACCTFROM><ACCTID>{card_id}</ACCTID></CCACCTFROM>
<BANKTRANLIST>
<DTSTART>20260401000000</DTSTART>
<DTEND>20260430000000</DTEND>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260410120000</DTPOSTED><TRNAMT>-89.90</TRNAMT><FITID>FC1</FITID><MEMO>IFOOD</MEMO></STMTTRN>
</BANKTRANLIST>
</CCSTMTRS>
</CCSTMTTRNRS>
</CREDITCARDMSGSRSV1>
</OFX>
""".encode()


# --------------------------------------------------------------------------------------
# bank_codes
# --------------------------------------------------------------------------------------


def test_resolves_known_bacen_codes() -> None:
    assert name_for_bank_code("260") == "Nubank"
    assert name_for_bank_code("341") == "Itaú"
    assert name_for_bank_code("237") == "Bradesco"


def test_resolves_with_leading_zeros() -> None:
    assert name_for_bank_code("0001") == "Banco do Brasil"
    assert name_for_bank_code(1) == "Banco do Brasil"


def test_unknown_code_returns_none() -> None:
    assert name_for_bank_code("999") is None
    assert name_for_bank_code(None) is None


# --------------------------------------------------------------------------------------
# inspect_ofx — checking account
# --------------------------------------------------------------------------------------


def test_inspects_checking_account() -> None:
    fp = inspect_ofx(_ofx_bank(bank_id="260", account_id="12345-6"))
    assert fp.bank_id == "260"
    assert fp.bank_name == "Nubank"
    assert fp.account_id == "12345-6"
    assert fp.account_kind == "checking"
    assert fp.transaction_count == 2
    assert fp.date_from == date(2026, 4, 15)
    assert fp.date_to == date(2026, 4, 20)


def test_unknown_bank_returns_none_name() -> None:
    fp = inspect_ofx(_ofx_bank(bank_id="999", account_id="x"))
    assert fp.bank_id == "999"
    assert fp.bank_name is None


# --------------------------------------------------------------------------------------
# inspect_ofx — credit card
# --------------------------------------------------------------------------------------


def test_inspects_credit_card_section() -> None:
    fp = inspect_ofx(_ofx_credit_card(bank_id="260", card_id="5555444433332222"))
    assert fp.bank_id == "260"
    assert fp.bank_name == "Nubank"
    assert fp.account_id == "5555444433332222"
    assert fp.account_kind == "credit_card"
    assert fp.transaction_count == 1


def test_label_format_is_human_readable() -> None:
    checking = inspect_ofx(_ofx_bank(bank_id="260", account_id="12345-6"))
    assert checking.label == "Nubank (account 12345-6)"

    card = inspect_ofx(_ofx_credit_card(bank_id="260", card_id="5555444433332222"))
    assert card.label == "Nubank (credit card 5555444433332222)"


# --------------------------------------------------------------------------------------
# Edge cases
# --------------------------------------------------------------------------------------


def test_invalid_ofx_raises_value_error() -> None:
    with pytest.raises(ValueError):
        inspect_ofx(b"isto nao eh ofx")
