"""Log redaction helpers (SECURITY.md: logs must never leak PII or secrets).

``redact()`` masks the sensitive patterns that realistically flow through this
app's log lines — API keys, bearer tokens, CPF, and long digit runs that look
like account numbers. ``RedactingFilter`` applies it to every record of a
logger tree; ``install_redaction()`` attaches it to the ``gastei`` logger and
is called once at app startup (``api.main.create_app``).

Deliberately conservative: false positives (masking a harmless number) are
cheap, false negatives (leaking a CPF) are not.
"""

from __future__ import annotations

import logging
import re

MASK = "***"

_PATTERNS: list[re.Pattern[str]] = [
    # Provider API keys / tokens (Anthropic, Google, GitHub, generic bearer).
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{30,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}"),
    # CPF — formatted (123.456.789-01) or bare 11-digit runs.
    re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    re.compile(r"\b\d{11}\b"),
    # Long digit runs (6+) — account numbers; amounts never reach this length.
    re.compile(r"\b\d{6,}\b"),
]


def redact(text: str) -> str:
    """Mask sensitive substrings. Idempotent and safe on arbitrary text."""
    for pattern in _PATTERNS:
        text = pattern.sub(MASK, text)
    return text


class RedactingFilter(logging.Filter):
    """Redacts the fully-formatted message of every record that passes through."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Collapse args into the message so redaction sees the final string.
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def install_redaction(logger_name: str = "gastei") -> None:
    """Attach the filter to a logger tree. Safe to call more than once."""
    logger = logging.getLogger(logger_name)
    if not any(isinstance(f, RedactingFilter) for f in logger.filters):
        logger.addFilter(RedactingFilter())
