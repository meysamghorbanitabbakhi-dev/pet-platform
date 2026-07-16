from __future__ import annotations

import logging

from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.time import utc_now
from app.modules.orders.models import Order
from app.modules.wallet.models import WalletCredit
from app.modules.wallet.service import WalletError, grant_late_delivery_credit

logger = logging.getLogger(__name__)


async def process_overdue_orders(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    batch_size: int = 100,
    basis_points: int = 500,
    expiry_months: int = 3,
) -> int:
    now = utc_now()
    async with session_factory() as session:
        credited_order_ids = select(WalletCredit.source_id).where(
            WalletCredit.source_type == "late_delivery"
        )
        orders = list(
            (
                await session.scalars(
                    select(Order)
                    .where(
                        Order.paid_at.is_not(None),
                        Order.delivery_commitment_at < now,
                        Order.status.not_in(("cancelled", "failed")),
                        ~Order.id.cast(String).in_(credited_order_ids),
                        (Order.delivered_at.is_(None))
                        | (Order.delivered_at > Order.delivery_commitment_at),
                    )
                    .order_by(Order.delivery_commitment_at)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        created = 0
        for order in orders:
            try:
                await grant_late_delivery_credit(
                    session,
                    order_id=order.id,
                    basis_points=basis_points,
                    expiry_months=expiry_months,
                )
            except WalletError:
                logger.exception("late credit failed for order %s", order.id)
            else:
                created += 1
        await session.commit()
        return created
