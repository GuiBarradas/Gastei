"""SQLAlchemy 2.0 engine, sessionmaker, and ``DeclarativeBase``.

Enables SQLite WAL mode and FK enforcement (ARCHITECTURE.md §2). For other
dialects the pool / listener configuration is a no-op.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from gastei.config import get_settings


class Base(DeclarativeBase):
    """Single declarative base shared across all models."""


def _build_engine(database_url: str) -> Engine:
    is_sqlite = database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine = create_engine(database_url, future=True, connect_args=connect_args)

    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _enable_sqlite_pragmas(dbapi_conn, _):  # pragma: no cover - infrastructure
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return engine


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _build_engine(get_settings().database_url)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False
        )
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager with automatic commit / rollback. For use outside FastAPI."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_for_tests(database_url: str) -> Engine:
    """Reset the engine singleton — **test use only**."""
    global _engine, _session_factory
    _engine = _build_engine(database_url)
    _session_factory = sessionmaker(
        bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    return _engine
