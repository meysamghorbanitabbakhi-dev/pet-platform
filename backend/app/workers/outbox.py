from __future__ import annotations

import asyncio
import logging
import signal

from app.common.time import utc_now
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.redis import close_redis, get_redis
from app.db.session import SessionFactory, close_database
from app.modules.notifications.service import (
    enqueue_concierge_offer_expired_notification,
    enqueue_concierge_offer_presented_notification,
    enqueue_concierge_offer_unavailable_notification,
    enqueue_replenishment_reservation_created_notification,
    enqueue_replenishment_reservation_expired_notification,
    enqueue_reservation_notification,
    enqueue_shelf_life_exception_notification,
    enqueue_wallet_credit_notification,
)
from app.modules.system.outbox import OutboxDispatcher

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings)
    dispatcher = OutboxDispatcher(SessionFactory, batch_size=settings.outbox_batch_size)
    dispatcher.register(
        "wallet.late_delivery_credit_granted",
        lambda payload: enqueue_wallet_credit_notification(
            SessionFactory,
            payload,
            customer_visible=settings.late_credit_customer_visible,
        ),
    )
    dispatcher.register(
        "orders.shelf_life_exception_proposed",
        lambda payload: enqueue_shelf_life_exception_notification(SessionFactory, payload),
    )
    dispatcher.register(
        "reservations.proposed",
        lambda payload: enqueue_reservation_notification(SessionFactory, payload),
    )
    dispatcher.register(
        "replenishment.reservation_created",
        lambda payload: enqueue_replenishment_reservation_created_notification(
            SessionFactory, payload
        ),
    )
    dispatcher.register(
        "replenishment.reservation_expired",
        lambda payload: enqueue_replenishment_reservation_expired_notification(
            SessionFactory, payload
        ),
    )
    dispatcher.register(
        "concierge.offer_presented",
        lambda payload: enqueue_concierge_offer_presented_notification(SessionFactory, payload),
    )
    dispatcher.register(
        "concierge.offer_unavailable",
        lambda payload: enqueue_concierge_offer_unavailable_notification(SessionFactory, payload),
    )
    dispatcher.register(
        "concierge.offer_expired",
        lambda payload: enqueue_concierge_offer_expired_notification(SessionFactory, payload),
    )
    redis = get_redis()
    stop = asyncio.Event()
    _install_stop_handlers(stop)
    logger.info("outbox worker started")
    try:
        while not stop.is_set():
            await redis.set("pet-platform:outbox-worker:heartbeat", utc_now().isoformat(), ex=90)
            processed = await dispatcher.dispatch_batch()
            if processed == 0:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=settings.outbox_poll_seconds)
                except TimeoutError:
                    pass
    finally:
        await close_redis()
        await close_database()


def _install_stop_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda *_: stop.set())


if __name__ == "__main__":
    asyncio.run(run())
