from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.redis import close_redis, get_redis
from app.db.session import SessionFactory, close_database
from app.integrations.otp.factory import OtpProviderNotConfiguredError, build_otp_provider
from app.integrations.price_intelligence.scheduler import run_price_intelligence_collection
from app.modules.notifications.service import deliver_pending_sms
from app.modules.orders.shelf_life_exceptions import expire_stale_shelf_life_exceptions
from app.modules.pet_knowledge.jobs import process_knowledge_review_lifecycle
from app.modules.replenishment.reservations import (
    expire_stale_reservations as expire_stale_replenishment_reservations,
)
from app.modules.replenishment.reservations import scan_and_create_due_reservations
from app.modules.reservations.service import expire_stale_reservations
from app.modules.wallet.jobs import process_overdue_orders

logger = logging.getLogger(__name__)
ScheduledJob = Callable[[], Awaitable[None]]


class Scheduler:
    def __init__(self) -> None:
        self._jobs: list[ScheduledJob] = []
        self._running = False

    def register(self, job: ScheduledJob) -> None:
        self._jobs.append(job)

    async def run_once(self) -> None:
        if self._running:
            logger.warning("scheduler run skipped because previous run is still active")
            return
        self._running = True
        for job in self._jobs:
            try:
                await job()
            except Exception:
                logger.exception("scheduler job failed")
        self._running = False


async def run() -> None:
    settings = get_settings()
    configure_logging(settings)
    scheduler = Scheduler()
    if settings.late_credit_enabled:
        scheduler.register(lambda: _run_overdue_credit_job())
    scheduler.register(lambda: _run_price_intelligence_job())
    scheduler.register(lambda: _run_pending_sms_job())
    scheduler.register(lambda: _run_knowledge_review_job())
    scheduler.register(lambda: _run_shelf_life_exception_expiry_job())
    if settings.reserve_now_enabled:
        scheduler.register(lambda: _run_reservation_expiry_job())
    if settings.replenishment_reservation_enabled:
        scheduler.register(lambda: _run_replenishment_scan_job())
        scheduler.register(lambda: _run_replenishment_expiry_job())
    redis = get_redis()
    stop = asyncio.Event()
    _install_stop_handlers(stop)
    logger.info("scheduler started")
    try:
        while not stop.is_set():
            await redis.set("pet-platform:scheduler:heartbeat", utc_heartbeat(), ex=90)
            lock = redis.lock("pet-platform:scheduler", timeout=300, blocking_timeout=1)
            acquired = await lock.acquire()
            if acquired:
                try:
                    await scheduler.run_once()
                finally:
                    try:
                        await lock.release()
                    except Exception:
                        logger.exception("scheduler lock release failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.scheduler_poll_seconds)
            except TimeoutError:
                pass
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


async def _run_shelf_life_exception_expiry_job() -> None:
    expired = await expire_stale_shelf_life_exceptions(SessionFactory)
    if expired:
        logger.info("expired %s unanswered shelf-life exceptions", expired)


async def _run_reservation_expiry_job() -> None:
    settings = get_settings()
    if not settings.reserve_now_enabled:
        return
    counts = await expire_stale_reservations(SessionFactory)
    if any(counts.values()):
        logger.info("expired stale reservations: %s", counts)


async def _run_replenishment_scan_job() -> None:
    settings = get_settings()
    if not settings.replenishment_reservation_enabled:
        return
    counts = await scan_and_create_due_reservations(
        SessionFactory,
        lead_days=settings.replenishment_reservation_lead_days,
        approval_window_hours=settings.replenishment_reservation_approval_window_hours,
    )
    if any(counts.values()):
        logger.info("replenishment reservation scan result: %s", counts)


async def _run_replenishment_expiry_job() -> None:
    settings = get_settings()
    if not settings.replenishment_reservation_enabled:
        return
    expired = await expire_stale_replenishment_reservations(SessionFactory)
    if expired:
        logger.info("expired %s stale replenishment reservations", expired)


async def _run_price_intelligence_job() -> None:
    result = await run_price_intelligence_collection()
    if result.get("status") not in {"disabled", "policy_blocked"}:
        logger.info("price intelligence collection result: %s", result)


def utc_heartbeat() -> str:
    from app.common.time import utc_now

    return utc_now().isoformat()


def _install_stop_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda *_: stop.set())


if __name__ == "__main__":
    asyncio.run(run())
