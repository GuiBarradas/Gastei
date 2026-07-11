"""Streamlit smoke tests — just verify that the pages render without raising.

We don't validate visual output or full flows (poor cost/benefit for a
volatile UI layer). The goal is to catch coarse regressions like "an import
broke".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


pytest.importorskip("streamlit.testing.v1", reason="Requer Streamlit ≥ 1.28")


STREAMLIT_DIR = Path(__file__).resolve().parents[2] / "streamlit_app"
if str(STREAMLIT_DIR) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_DIR))


class FakeApi:
    """ApiClient fake — devolve listas/dicts vazios. Suficiente pro smoke."""

    base_url = "http://test"

    def health(self):
        return {"status": "ok"}

    def list_items(self):
        return []

    def list_accounts(self):
        return []

    def list_transactions(self, *args, **kwargs):
        return []

    def list_categories(self):
        return []

    def update_category(self, *args, **kwargs):
        return {"status": "ok"}

    def recategorize_pending(self, *args, **kwargs):
        return {"candidates": 0, "categorized": 0, "skipped": 0}

    def delete_item(self, *args, **kwargs):
        return None

    def spending_by_category(self, *args, **kwargs):
        return []

    def monthly_summary(self, *args, **kwargs):
        return []

    def top_merchants(self, *args, **kwargs):
        return []

    def balances_by_bank(self, *args, **kwargs):
        return []

    def import_ofx(self, *args, **kwargs):
        return {"imported": 0, "duplicates": 0, "errors": []}

    def inspect_ofx(self, *args, **kwargs):
        return {
            "bank_id": "260",
            "bank_name": "Nubank",
            "account_id": "12345",
            "account_kind": "checking",
            "transaction_count": 0,
            "date_from": None,
            "date_to": None,
        }

    def chat(self, *args, **kwargs):
        return {
            "conversation_id": 1,
            "answer": "ok",
            "tool_calls": [],
            "iterations": 1,
            "tokens_input": 0,
            "tokens_output": 0,
        }

    def list_conversations(self):
        return []

    def list_messages(self, *args, **kwargs):
        return []

    def sync_all(self):
        return {
            "items_synced": 0,
            "accounts_synced": 0,
            "transactions_imported": 0,
            "transactions_duplicates": 0,
            "transactions_categorized": 0,
            "errors": [],
        }


@pytest.fixture
def patched_api(monkeypatch: pytest.MonkeyPatch) -> FakeApi:
    fake = FakeApi()
    # Importa via bare path (mesma forma que Streamlit importa em runtime)
    import components.api_client as api_module  # type: ignore[import-not-found]

    # Limpa cache do @st.cache_resource antes de patchar
    if hasattr(api_module.get_api_client, "clear"):
        api_module.get_api_client.clear()
    monkeypatch.setattr(api_module, "get_api_client", lambda: fake)
    return fake


def test_router_and_home_render(patched_api: FakeApi) -> None:
    """app.py = router (st.navigation); running it executes the default view (home)."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("streamlit_app/app.py")
    at.run(timeout=30)
    assert not at.exception, f"App quebrou: {at.exception}"


def test_dashboard_page_renders_without_data(patched_api: FakeApi) -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("streamlit_app/views/dashboard.py")
    at.run(timeout=30)
    assert not at.exception, f"Dashboard quebrou: {at.exception}"


def test_transactions_page_renders_without_data(patched_api: FakeApi) -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("streamlit_app/views/transacoes.py")
    at.run(timeout=30)
    assert not at.exception, f"Transações quebrou: {at.exception}"


def test_conexoes_page_renders_without_data(patched_api: FakeApi) -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("streamlit_app/views/conexoes.py")
    at.run(timeout=30)
    assert not at.exception, f"Conexões quebrou: {at.exception}"


def test_chat_page_renders_without_data(patched_api: FakeApi) -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("streamlit_app/views/chat.py")
    at.run(timeout=30)
    assert not at.exception, f"Chat quebrou: {at.exception}"
