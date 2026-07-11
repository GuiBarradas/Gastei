"""Global pytest fixtures.

Conventions (ARCHITECTURE.md §8):

- ``db_url`` is a function-scoped fixture pointing at a SQLite tmpfile
  (in-memory has caveats around Alembic and multiple connections).
- ``db_session`` applies ``alembic upgrade head`` and yields a ready-to-use ``Session``.
- Markers: ``unit`` (default) | ``integration`` | ``contract`` | ``slow``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    """SQLite tmpfile, isolated per test."""
    db_file = tmp_path / "test.db"
    return f"sqlite:///{db_file}"


@pytest.fixture
def alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture
def migrated_db(db_url: str, alembic_cfg: Config, monkeypatch: pytest.MonkeyPatch) -> str:
    """Database with the full schema applied."""
    monkeypatch.setenv("DATABASE_URL", db_url)
    command.upgrade(alembic_cfg, "head")
    return db_url


@pytest.fixture
def db_session(migrated_db: str) -> Iterator[Session]:
    engine = create_engine(migrated_db, future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session
    engine.dispose()
