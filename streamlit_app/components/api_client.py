"""``httpx`` wrapper for the FastAPI backend. Cached per Streamlit session."""

from __future__ import annotations

import os
from datetime import date
from typing import Any

import httpx
import streamlit as st

DEFAULT_BASE_URL = "http://localhost:8000"


class ApiClient:
    """Cliente HTTP sync do backend Gastei."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = base_url or os.environ.get("GASTEI_API_URL", DEFAULT_BASE_URL)
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    # ---------- Health ----------
    def health(self) -> dict[str, str]:
        r = self._client.get("/health")
        r.raise_for_status()
        return r.json()

    # ---------- Items / Accounts ----------
    def list_items(self) -> list[dict[str, Any]]:
        r = self._client.get("/items")
        r.raise_for_status()
        return r.json()

    def list_accounts(self) -> list[dict[str, Any]]:
        r = self._client.get("/accounts")
        r.raise_for_status()
        return r.json()

    # ---------- Transactions ----------
    def list_transactions(
        self,
        account_id: str | None = None,
        item_id: str | None = None,
        start: date | None = None,
        end: date | None = None,
        category: str | None = None,
        search: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if account_id:
            params["account_id"] = account_id
        if item_id:
            params["item_id"] = item_id
        if start:
            params["start"] = start.isoformat()
        if end:
            params["end"] = end.isoformat()
        if category:
            params["category"] = category
        if search:
            params["search"] = search
        r = self._client.get("/transactions", params=params)
        r.raise_for_status()
        return r.json()

    def list_categories(self) -> list[dict[str, Any]]:
        r = self._client.get("/categories")
        r.raise_for_status()
        return r.json()

    def update_category(self, tx_id: str, category: str) -> dict[str, Any]:
        r = self._client.patch(f"/transactions/{tx_id}", json={"category": category})
        r.raise_for_status()
        return r.json()

    def recategorize_pending(self, limit: int = 500) -> dict[str, Any]:
        r = self._client.post(
            "/transactions/recategorize",
            params={"limit": limit},
            timeout=300.0,
        )
        r.raise_for_status()
        return r.json()

    def delete_item(self, item_id: str) -> None:
        r = self._client.delete(f"/items/{item_id}")
        r.raise_for_status()

    # ---------- Insights ----------
    def _insights_params(
        self,
        account_id: str | None,
        item_id: str | None,
        start: date | None,
        end: date | None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        p: dict[str, Any] = dict(extra or {})
        if account_id:
            p["account_id"] = account_id
        if item_id:
            p["item_id"] = item_id
        if start:
            p["start"] = start.isoformat()
        if end:
            p["end"] = end.isoformat()
        return p

    def spending_by_category(
        self,
        account_id: str | None = None,
        item_id: str | None = None,
        start: date | None = None,
        end: date | None = None,
        top_n: int = 8,
    ) -> list[dict[str, Any]]:
        params = self._insights_params(account_id, item_id, start, end, {"top_n": top_n})
        r = self._client.get("/insights/spending-by-category", params=params)
        r.raise_for_status()
        return r.json()

    def monthly_summary(
        self,
        account_id: str | None = None,
        item_id: str | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict[str, Any]]:
        params = self._insights_params(account_id, item_id, start, end)
        r = self._client.get("/insights/monthly-summary", params=params)
        r.raise_for_status()
        return r.json()

    def top_merchants(
        self,
        account_id: str | None = None,
        item_id: str | None = None,
        start: date | None = None,
        end: date | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        params = self._insights_params(account_id, item_id, start, end, {"limit": limit})
        r = self._client.get("/insights/top-merchants", params=params)
        r.raise_for_status()
        return r.json()

    def balances_by_bank(self) -> list[dict[str, Any]]:
        r = self._client.get("/insights/balances-by-bank")
        r.raise_for_status()
        return r.json()

    # ---------- Imports ----------
    def import_ofx(
        self,
        file_bytes: bytes,
        account_id: str | None = None,
        filename: str = "extrato.ofx",
    ) -> dict[str, Any]:
        """account_id=None → auto-resolve via banco/conta no OFX."""
        files = {"file": (filename, file_bytes, "application/x-ofx")}
        data = {"account_id": account_id} if account_id else {}
        r = self._client.post("/imports/ofx", data=data, files=files)
        r.raise_for_status()
        return r.json()

    def inspect_ofx(self, file_bytes: bytes, filename: str = "extrato.ofx") -> dict[str, Any]:
        files = {"file": (filename, file_bytes, "application/x-ofx")}
        r = self._client.post("/imports/ofx/inspect", files=files)
        r.raise_for_status()
        return r.json()

    # ---------- Chat ----------
    def chat(self, message: str, conversation_id: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"message": message}
        if conversation_id is not None:
            payload["conversation_id"] = conversation_id
        r = self._client.post("/chat", json=payload, timeout=120.0)
        r.raise_for_status()
        return r.json()

    def list_conversations(self) -> list[dict[str, Any]]:
        r = self._client.get("/chat/conversations")
        r.raise_for_status()
        return r.json()

    def list_messages(self, conversation_id: int) -> list[dict[str, Any]]:
        r = self._client.get(f"/chat/conversations/{conversation_id}/messages")
        r.raise_for_status()
        return r.json()

    # ---------- Sync (Pluggy) ----------
    def sync_all(self) -> dict[str, Any]:
        r = self._client.post("/sync", timeout=300.0)
        r.raise_for_status()
        return r.json()


@st.cache_resource
def get_api_client() -> ApiClient:
    """Singleton compartilhado entre páginas."""
    return ApiClient()
