"""APScheduler sync-job specs — critical paths only.

Validates: the scheduler is built, the job is registered, the interval is
correct, and the ``ENABLE_SCHEDULER`` flag is honored.
"""

from __future__ import annotations

import pytest

from gastei.jobs.sync_job import build_scheduler

pytestmark = pytest.mark.unit


def test_scheduler_registers_sync_job() -> None:
    scheduler = build_scheduler()
    jobs = scheduler.get_jobs()

    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "pluggy_sync_all"
    assert job.max_instances == 1
    assert job.coalesce is True


def test_scheduler_uses_configured_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNC_INTERVAL_HOURS", "12")
    # Reset cached settings
    from gastei.config import get_settings

    get_settings.cache_clear()

    scheduler = build_scheduler()
    job = scheduler.get_jobs()[0]
    # Interval trigger expõe interval em segundos
    assert job.trigger.interval.total_seconds() == 12 * 3600

    get_settings.cache_clear()


def test_scheduler_lifespan_no_op_when_disabled() -> None:
    """Quando enable_scheduler=False, o lifespan deve apenas yield sem erro."""
    import asyncio

    from gastei.config import get_settings
    from gastei.jobs.sync_job import scheduler_lifespan

    get_settings.cache_clear()  # garante leitura limpa do .env (default False)

    async def _exercise() -> None:
        async with scheduler_lifespan(app=None):
            pass  # ok se não explodiu

    asyncio.run(_exercise())
    get_settings.cache_clear()
