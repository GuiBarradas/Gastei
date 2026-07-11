"""APScheduler — recurring sync job through Pluggy.

Started by the FastAPI lifespan in ``gastei.api.main``. Opt-in via
``ENABLE_SCHEDULER=true`` in ``.env``; in development and tests we
keep it off so we don't fire external calls implicitly.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from gastei.api.deps import (
    build_classifier,
    get_bank_connector,
    get_llm_client,
    get_pluggy_client,
)
from gastei.config import get_settings
from gastei.db import get_sessionmaker
from gastei.repositories.account_repo import AccountRepository, ItemRepository
from gastei.repositories.transaction_repo import SQLAlchemyTransactionRepository
from gastei.services.sync_service import SyncService

logger = logging.getLogger(__name__)


async def run_sync_job() -> None:
    """Create an isolated session, build the service, run ``sync_all``.

    Runs outside the FastAPI request cycle so it must own its own DB session
    and HTTP client lifetimes.
    """
    pluggy = get_pluggy_client()
    if pluggy is None:
        logger.info("Sync job: Pluggy is not configured, skipping")
        return

    bank = get_bank_connector(client=pluggy)
    if bank is None:
        return

    session_factory = get_sessionmaker()
    session = session_factory()
    try:
        service = SyncService(
            bank=bank,
            tx_repo=SQLAlchemyTransactionRepository(session),
            account_repo=AccountRepository(session),
            item_repo=ItemRepository(session),
            # ``Depends`` defaults don't resolve outside FastAPI — build explicitly.
            classifier=build_classifier(session, get_llm_client()),
        )
        result = await service.sync_all()
        logger.info(
            "Sync job done: %d items, %d accounts, %d new tx, %d duplicates, %d categorized",
            result.items_synced,
            result.accounts_synced,
            result.transactions_imported,
            result.transactions_duplicates,
            result.transactions_categorized,
        )
        if result.errors:
            for err in result.errors:
                logger.warning("Sync job partial error: %s", err)
    except Exception:
        logger.exception("Sync job failed")
    finally:
        session.close()
        await pluggy.aclose()


def build_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        run_sync_job,
        trigger="interval",
        hours=settings.sync_interval_hours,
        id="pluggy_sync_all",
        replace_existing=True,
        max_instances=1,  # never run two syncs in parallel
        coalesce=True,
    )
    return scheduler


@asynccontextmanager
async def scheduler_lifespan(app: Any):
    """FastAPI lifespan that toggles the scheduler based on ``ENABLE_SCHEDULER``."""
    settings = get_settings()
    if not settings.enable_scheduler:
        logger.info("Scheduler disabled (ENABLE_SCHEDULER=false)")
        yield
        return

    scheduler = build_scheduler()
    scheduler.start()
    logger.info(
        "Scheduler started — sync every %d hour(s)",
        settings.sync_interval_hours,
    )
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
