"""Integration tests for ``GET /categories`` (taxonomy read endpoint)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from gastei.api.deps import get_db_session
from gastei.api.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app = create_app()

    def _override_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_list_categories_returns_seeded_taxonomy(client: TestClient) -> None:
    r = client.get("/categories")
    assert r.status_code == 200
    body = r.json()

    codes = {c["code"] for c in body}
    # Seeded by migration 0001 from seeds/categories.yaml.
    assert "alimentacao.delivery" in codes
    assert "outros.diversos" in codes

    delivery = next(c for c in body if c["code"] == "alimentacao.delivery")
    assert delivery["label"]  # human label present for UI dropdowns
    assert delivery["is_income"] is False

    salario = next(c for c in body if c["code"] == "renda.salario")
    assert salario["is_income"] is True

    # Sorted by code — stable ordering for pickers.
    assert [c["code"] for c in body] == sorted(codes)
