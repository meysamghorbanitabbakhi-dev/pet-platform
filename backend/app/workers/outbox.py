from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionFactory, close_database
from app.modules.notifications.service import enqueue_wallet_credit_notification
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
    logger.info("outbox worker started")
    try:
        while True:
            processed = await dispatcher.dispatch_batch()
            if processed == 0:
                await asyncio.sleep(settings.outbox_poll_seconds)
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(run())
