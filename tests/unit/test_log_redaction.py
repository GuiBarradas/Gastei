"""Log redaction specs (SECURITY.md: no PII or secrets in logs)."""

from __future__ import annotations

import logging

import pytest

from gastei.utils.logging import MASK, RedactingFilter, install_redaction, redact

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "leaked"),
    [
        ("key=sk-ant-api03-abcdefghijklmnop1234", "sk-ant"),
        ("GOOGLE_API_KEY=AIzaFakeKey0000000000000000000000000000", "AIza"),
        ("token ghp_abcdefghijklmnopqrstuvwxyz012345", "ghp_"),
        ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc", "eyJ"),
        ("cliente CPF 123.456.789-01 pagou", "123.456"),
        ("cpf bare 12345678901 ok", "12345678901"),
        ("conta 0012345-6 do banco", "0012345"),
    ],
)
def test_redact_masks_sensitive_patterns(raw: str, leaked: str) -> None:
    cleaned = redact(raw)
    assert leaked not in cleaned
    assert MASK in cleaned


def test_redact_leaves_ordinary_text_alone() -> None:
    text = "imported 78 tx, 12 duplicates for item ofx-260 on 2026-07-10"
    assert redact(text) == text


def test_filter_redacts_formatted_records(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("gastei.test_redaction")
    logger.addFilter(RedactingFilter())
    with caplog.at_level(logging.INFO, logger="gastei.test_redaction"):
        logger.info("refreshing with key %s", "AIzaFakeKey0000000000000000000000000000")
    assert "AIza" not in caplog.text
    assert MASK in caplog.text


def test_install_redaction_is_idempotent() -> None:
    name = "gastei.test_redaction_idem"
    install_redaction(name)
    install_redaction(name)
    filters = logging.getLogger(name).filters
    assert sum(isinstance(f, RedactingFilter) for f in filters) == 1
