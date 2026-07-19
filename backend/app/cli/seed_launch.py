from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.session import SessionFactory, close_database
from app.modules.notifications.models import NotificationTemplate


async def seed() -> int:
    async with SessionFactory() as session:
        existing = await session.scalar(
            select(NotificationTemplate).where(
                NotificationTemplate.event_key == "wallet.late_credit_granted",
                NotificationTemplate.channel == "sms",
                NotificationTemplate.version == 1,
            )
        )
        if existing is not None:
            return 0
        session.add(
            NotificationTemplate(
                event_key="wallet.late_credit_granted",
                channel="sms",
                version=1,
                body_fa=(
                    "برای تأخیر سفارش {order_id}، مبلغ {amount_irr} ریال به کیف پول شما "
                    "افزوده شد. اعتبار تا {expires_at}."
                ),
                active=False,
            )
        )
        await session.commit()
        return 1


async def _run() -> None:
    try:
        created = await seed()
        print(f"launch_fixtures_ready created={created}")
    finally:
        await close_database()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
