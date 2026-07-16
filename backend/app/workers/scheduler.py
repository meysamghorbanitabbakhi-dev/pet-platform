from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.redis import close_redis, get_redis
from app.db.session import SessionFactory, close_database
from app.integrations.otp.factory import OtpProviderNotConfiguredError, build_otp_provider
from app.modules.notifications.service import deliver_pending_sms
from app.modules.pet_knowledge.jobs import process_knowledge_review_lifecycle
from app.modules.wallet.jobs import process_overdue_orders

logger = logging.getLogger(__name__)
ScheduledJob = Callable[[], Awaitable[None]]


class Scheduler:
    def __init__(self) -> None:
        self._jobs: list[ScheduledJob] = []

    def register(self, job: ScheduledJob) -> None:
        self._jobs.append(job)

    async def run_once(self) -> None:
        for job in self._jobs:
            await job()


async def run() -> None:
    settings = get_settings()
    configure_logging(settings)
    scheduler = Scheduler()
    if settings.late_credit_enabled:
        scheduler.register(lambda: _run_overdue_credit_job())
    scheduler.register(lambda: _run_pending_sms_job())
    scheduler.register(lambda: _run_knowledge_review_job())
    redis = get_redis()
    logger.info("scheduler started")
    try:
        while True:
            lock = redis.lock("pet-platform:scheduler", timeout=30, blocking_timeout=1)
            acquired = await lock.acquire()
            if acquired:
                try:
                    await scheduler.run_once()
                finally:
                    await lock.release()
            await asyncio.sleep(settings.scheduler_poll_seconds)
    finally:
        await close_redis()
        await close_database()


async def _run_overdue_credit_job() -> None:
    settings = get_settings()
    if not settings.late_credit_enabled:
        return
    created = await process_overdue_orders(
        SessionFactory,
        basis_points=settings.late_credit_basis_points,
        expiry_months=settings.late_credit_expiry_months,
    )
    if created:
        logger.info("created %s overdue-order wallet credits", created)


async def _run_pending_sms_job() -> None:
    settings = get_settings()
    try:
        provider = build_otp_provider(settings)
    except OtpProviderNotConfiguredError:
        return
    try:
        sent = await deliver_pending_sms(SessionFactory, provider)
        if sent:
            logger.info("sent %s transactional SMS notifications", sent)
    finally:
        await provider.aclose()


async def _run_knowledge_review_job() -> None:
    counts = await process_knowledge_review_lifecycle(SessionFactory)
    if any(counts.values()):
        logger.info("processed knowledge review lifecycle: %s", counts)


if __name__ == "__main__":
    asyncio.run(run())
