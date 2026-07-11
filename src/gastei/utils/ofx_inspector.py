"""Extract metadata from an OFX file without persisting anything.

Used to preview an upload before importing ("this file is from Nubank,
account XXX") and to power the auto-resolve path in ``OFXImportService``.

Implementation note: this uses targeted regular expressions over the raw
SGML rather than fully parsing with ``ofxparse``. ``ofxparse`` exposes
credit-card metadata inconsistently across versions, and a regex scan is
both simpler and more robust for the small set of fields we need.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from gastei.schemas.ofx import OFXFingerprint
from gastei.utils.bank_codes import name_for_bank_code

# OFX 1.x SGML patterns. Open tag, value runs until the next ``<`` or whitespace.
_BANK_BLOCK = re.compile(r"<BANKACCTFROM>(.*?)</BANKACCTFROM>", re.IGNORECASE | re.DOTALL)
_CC_BLOCK = re.compile(r"<CCACCTFROM>(.*?)</CCACCTFROM>", re.IGNORECASE | re.DOTALL)
_BANKID = re.compile(r"<BANKID>\s*([^\s<]+)", re.IGNORECASE)
_ACCTID = re.compile(r"<ACCTID>\s*([^\s<]+)", re.IGNORECASE)
_FID = re.compile(r"<FID>\s*([^\s<]+)", re.IGNORECASE)
_STMTTRN = re.compile(r"<STMTTRN\b", re.IGNORECASE)
_DTPOSTED = re.compile(r"<DTPOSTED>\s*(\d{8})", re.IGNORECASE)


def _decode(file_bytes: bytes) -> str:
    """Brazilian OFX files typically use latin-1 / cp1252; UTF-8 also occurs."""
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return file_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("latin-1", errors="replace")


def _first(pattern: re.Pattern[str], text: str) -> str | None:
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def inspect_ofx(file_bytes: bytes) -> OFXFingerprint:
    """Parse the OFX file via regex and return a fingerprint.

    Raises ``ValueError`` if the file does not look like OFX.
    """
    text = _decode(file_bytes)

    if "<OFX>" not in text.upper():
        raise ValueError("Invalid OFX: <OFX> tag not found")

    # Account kind: whichever block appears first.
    bank_block = _BANK_BLOCK.search(text)
    cc_block = _CC_BLOCK.search(text)

    bank_id: str | None = None
    account_id: str | None = None
    kind: str = "unknown"

    if cc_block:
        kind = "credit_card"
        account_id = _first(_ACCTID, cc_block.group(1))
    elif bank_block:
        kind = "checking"
        account_id = _first(_ACCTID, bank_block.group(1))
        bank_id = _first(_BANKID, bank_block.group(1))

    # FID inside SIGNONMSGSRSV1 covers the credit-card case (no BANKID in CC blocks).
    if not bank_id:
        bank_id = _first(_FID, text)

    # Transaction count + date range.
    tx_matches = _STMTTRN.findall(text)
    tx_count = len(tx_matches)

    dates: list[date] = []
    for m in _DTPOSTED.finditer(text):
        try:
            d = datetime.strptime(m.group(1), "%Y%m%d").date()
            dates.append(d)
        except ValueError:
            continue

    return OFXFingerprint(
        bank_id=bank_id,
        bank_name=name_for_bank_code(bank_id),
        account_id=account_id,
        account_kind=kind,  # type: ignore[arg-type]
        transaction_count=tx_count,
        date_from=min(dates) if dates else None,
        date_to=max(dates) if dates else None,
    )
