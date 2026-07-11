"""PluggyClient — async HTTP wrapper over the Pluggy Data API.

We don't use the official ``pluggy-sdk`` because it is synchronous and we
want async throughout the FastAPI stack. The API key has a ~2-hour lifetime;
we refresh lazily under an ``asyncio.Lock`` to avoid thundering-herd refreshes.

Reference: https://docs.pluggy.ai/reference/welcome
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PluggyAuthError(Exception):
    """Authentication failed (HTTP 401, bad credentials)."""


class PluggyError(Exception):
    """Generic API error (4xx / 5xx other than 401)."""


class PluggyClient:
    BASE_URL = "https://api.pluggy.ai"
    # API key TTL is 2h; refresh ~10 min ahead of expiry to leave margin.
    KEY_TTL = timedelta(hours=1, minutes=50)

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = httpx.AsyncClient(base_url=base_url or self.BASE_URL, timeout=timeout)
        self._api_key: str | None = None
        self._api_key_expires_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> PluggyClient:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def _ensure_api_key(self) -> str:
        async with self._lock:
            now = datetime.now()
            if (
                self._api_key is not None
                and self._api_key_expires_at is not None
                and now < self._api_key_expires_at
            ):
                return self._api_key

            resp = await self._http.post(
                "/auth",
                json={
                    "clientId": self._client_id,
                    "clientSecret": self._client_secret,
                },
            )
            if resp.status_code == 401:
                raise PluggyAuthError("Invalid Pluggy credentials (HTTP 401)")
            resp.raise_for_status()
            data = resp.json()
            self._api_key = data["apiKey"]
            self._api_key_expires_at = now + self.KEY_TTL
            logger.info("Pluggy API key refreshed (valid until %s)", self._api_key_expires_at)
            return self._api_key

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        api_key = await self._ensure_api_key()
        headers = {"X-API-KEY": api_key, "accept": "application/json"}
        resp = await self._http.request(method, path, params=params, json=json, headers=headers)
        if resp.status_code == 401:
            # API key may have expired mid-request — force-refresh and retry once.
            self._api_key = None
            api_key = await self._ensure_api_key()
            headers["X-API-KEY"] = api_key
            resp = await self._http.request(method, path, params=params, json=json, headers=headers)
        if resp.status_code >= 400:
            raise PluggyError(f"{method} {path} → {resp.status_code}: {resp.text[:200]}")
        return resp.json() if resp.content else {}

    # ------------------------------------------------------------------
    # Items / Accounts / Transactions
    # ------------------------------------------------------------------

    async def list_items(self) -> list[dict[str, Any]]:
        """GET /items. The API returns ``{results: [...], total, page, totalPages}``.

        On freshly-created Development apps without any connected item,
        this endpoint can return HTTP 401 (a known Pluggy quirk — auth
        succeeds, but listing is denied). We treat that case as "no items":
        the semantic outcome is the same.
        """
        try:
            data = await self._request("GET", "/items")
        except PluggyError as exc:
            if " 401:" in str(exc) or " 403:" in str(exc):
                logger.warning(
                    "Pluggy /items returned 401/403 — likely no items connected yet. "
                    "Use the Connect Widget to add one."
                )
                return []
            raise

        results = data.get("results")
        if isinstance(results, list):
            return results
        if isinstance(data, dict) and "id" in data:
            return [data]
        return []

    async def list_connectors(self) -> list[dict[str, Any]]:
        """GET /connectors — list of supported banks. Always accessible."""
        data = await self._request("GET", "/connectors")
        return data.get("results", [])

    async def get_item(self, item_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/items/{item_id}")

    async def list_accounts(self, item_id: str) -> list[dict[str, Any]]:
        data = await self._request("GET", "/accounts", params={"itemId": item_id})
        return data.get("results", [])

    async def list_transactions(
        self,
        account_id: str,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        page_size: int = 500,
    ) -> dict[str, Any]:
        """Returns the raw Pluggy JSON envelope (``results``, ``total``, ``totalPages``, ``page``)."""
        params: dict[str, Any] = {
            "accountId": account_id,
            "page": page,
            "pageSize": page_size,
        }
        if date_from:
            params["from"] = date_from
        if date_to:
            params["to"] = date_to
        return await self._request("GET", "/transactions", params=params)

    async def trigger_sync(self, item_id: str) -> dict[str, Any]:
        """Pluggy: ``PATCH /items/{id}`` kicks off a new collection."""
        return await self._request("PATCH", f"/items/{item_id}")

    async def create_connect_token(
        self,
        item_id: str | None = None,
        client_user_id: str | None = None,
    ) -> str:
        """30-minute token used by the Connect Widget on the frontend."""
        body: dict[str, Any] = {}
        if item_id:
            body["itemId"] = item_id
        if client_user_id:
            body["clientUserId"] = client_user_id
        data = await self._request("POST", "/connect_token", json=body)
        return data["accessToken"]
