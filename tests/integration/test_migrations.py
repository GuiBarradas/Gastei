"""Integration test: ``alembic upgrade head`` + ``downgrade base``.

Validates:

1. The initial migration creates all 9 tables plus ``alembic_version``.
2. The expected indexes exist (including the partial ``idx_tx_uncategorized``).
3. The category seed is inserted with consistent foreign keys.
4. ``downgrade base`` is reversible (clears everything except ``alembic_version``).
"""

from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.integration


EXPECTED_TABLES = {
    "items",
    "accounts",
    "transactions",
    "categories",
    "rules",
    "examples",
    "insight_cache",
    "conversations",
    "messages",
}

EXPECTED_INDEXES_BY_TABLE = {
    "accounts": {"idx_accounts_item"},
    "transactions": {"idx_tx_account_date", "idx_tx_category", "idx_tx_uncategorized"},
    "rules": {"idx_rules_priority"},
    "examples": {"idx_examples_recent"},
}


def test_upgrade_head_creates_all_tables(migrated_db: str) -> None:
    engine = create_engine(migrated_db, future=True)
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    missing = EXPECTED_TABLES - tables
    assert not missing, f"Tabelas faltando: {missing}"
    assert "alembic_version" in tables


def test_upgrade_head_creates_expected_indexes(migrated_db: str) -> None:
    engine = create_engine(migrated_db, future=True)
    insp = inspect(engine)

    for table, expected in EXPECTED_INDEXES_BY_TABLE.items():
        actual = {idx["name"] for idx in insp.get_indexes(table)}
        missing = expected - actual
        assert not missing, f"Índices faltando em {table}: {missing} (encontrados: {actual})"


def test_partial_index_uncategorized_has_where_clause(migrated_db: str) -> None:
    """idx_tx_uncategorized é parcial (WHERE category IS NULL).

    SQLite expõe a definição via sqlite_master.
    """
    engine = create_engine(migrated_db, future=True)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_tx_uncategorized'")
        ).first()
    assert row is not None, "Índice parcial não foi criado"
    sql = row[0].lower()
    assert "where" in sql and "category is null" in sql, (
        f"Índice não tem WHERE clause esperada: {row[0]}"
    )


def test_categories_seed_loaded(migrated_db: str) -> None:
    engine = create_engine(migrated_db, future=True)
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM categories")).scalar_one()
        roots = conn.execute(
            text("SELECT COUNT(*) FROM categories WHERE parent_code IS NULL")
        ).scalar_one()
        income_kids = conn.execute(
            text("SELECT COUNT(*) FROM categories WHERE is_income = 1")
        ).scalar_one()
        orphans = conn.execute(
            text(
                "SELECT COUNT(*) FROM categories c "
                "WHERE parent_code IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM categories p WHERE p.code = c.parent_code)"
            )
        ).scalar_one()

    assert total > 30, f"Esperado >30 categorias, achou {total}"
    assert roots == 11, f"Esperado 11 raízes, achou {roots}"
    assert income_kids >= 4, f"Esperado pelo menos 4 categorias is_income, achou {income_kids}"
    assert orphans == 0, "FKs self-referenciais consistentes"


def test_downgrade_base_drops_all_app_tables(alembic_cfg: Config, migrated_db: str) -> None:
    command.downgrade(alembic_cfg, "base")
    engine = create_engine(migrated_db, future=True)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    leftover = tables & EXPECTED_TABLES
    assert not leftover, f"Tabelas não removidas no downgrade: {leftover}"
