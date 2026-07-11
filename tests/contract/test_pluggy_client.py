"""``PluggyClient`` contract test — real call against the sandbox.

Skipped by default. To run::

    uv run pytest -m contract tests/contract/test_pluggy_client.py

Required environment variables (or ``.env`` entries)::

    PLUGGY_CLIENT_ID=...
    PLUGGY_CLIENT_SECRET=...

Obtain credentials at https://dashboard.pluggy.ai/ → API Keys
(sandbox tier is free, no card required).
"""

from __future__ import annotations

import unicodedata

import pytest

from gastei.clients.pluggy_client import PluggyClient
from gastei.config import get_settings

pytestmark = [
    pytest.mark.contract,
    pytest.mark.skipif(
        not (get_settings().pluggy_client_id and get_settings().pluggy_client_secret),
        reason="No Pluggy credentials in .env",
    ),
]


@pytest.fixture
async def pluggy() -> PluggyClient:
    settings = get_settings()
    client = PluggyClient(
        client_id=settings.pluggy_client_id,
        client_secret=settings.pluggy_client_secret,
        base_url=settings.pluggy_base_url,
    )
    yield client
    await client.aclose()


def _ascii_fold(text: str) -> str:
    """Strip diacritics so 'Itaú' matches 'itau'."""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    ).lower()


async def test_auth_returns_api_key(pluggy: PluggyClient) -> None:
    key = await pluggy._ensure_api_key()
    assert key, "API key was empty"
    assert isinstance(key, str)


async def test_list_connectors_returns_non_empty_list(
    pluggy: PluggyClient,
) -> None:
    """``/connectors`` is universally accessible — proves auth + request work.

    We avoid ``/items`` here because it requires a connected item (created via
    the Connect Widget). On a fresh app, ``/items`` would yield a false
    negative even though auth and HTTP plumbing are healthy.

    The exact set of connectors returned depends on the app's tier and
    sandbox configuration, so we only assert structural shape: a non-empty
    list of dicts, each carrying at least an ``id`` and a ``name``.
    """
    connectors = await pluggy.list_connectors()
    assert isinstance(connectors, list)
    assert len(connectors) > 0, "Pluggy should expose at least one connector"
    for c in connectors:
        assert isinstance(c, dict)
        assert "id" in c
        assert _ascii_fold(c.get("name", "")) != ""
