from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.catalog.models import CatalogAvailabilitySubscription, Offer
from app.modules.notifications.models import Notification
from app.modules.system.outbox import DomainEvent, add_outbox_event


async def notify_available_subscribers(session: AsyncSession, offer: Offer) -> int:
    if (
        offer.status != "active"
        or offer.stock_posture != "sourced_after_payment"
        or offer.sourcing_capacity_status != "open"
        # concierge_only offers are bound to one specific customer/request
        # and must never be discovered through the generic availability-
        # subscription path regardless of state -- matches the same
        # exclusion list/search/detail/subscribe all apply
        # (app.modules.catalog.eligibility).
        or offer.mode == "concierge_only"
    ):
        return 0
    now = utc_now()
    if offer.available_from is not None and offer.available_from > now:
        return 0
    if offer.available_until is not None and offer.available_until <= now:
        return 0
    subscriptions = list(
        (
            await session.scalars(
                select(CatalogAvailabilitySubscription)
                .where(
                    CatalogAvailabilitySubscription.offer_id == offer.id,
                    CatalogAvailabilitySubscription.status == "active",
                )
                .with_for_update()
            )
        ).all()
    )
    sent = 0
    for subscription in subscriptions:
        source_id = f"{subscription.id}:{subscription.activation_cycle}"
        for channel in ("in_app", "sms"):
            existing = await session.scalar(
                select(Notification).where(
                    Notification.event_key == "catalog.offer_available",
                    Notification.source_id == source_id,
                    Notification.recipient_identity_id == subscription.identity_id,
                    Notification.channel == channel,
                )
            )
            if existing is None:
                session.add(
                    Notification(
                        recipient_identity_id=subscription.identity_id,
                        event_key="catalog.offer_available",
                        source_id=source_id,
                        channel=channel,
                        payload={"offer_id": str(offer.id), "order_created": False},
                        status="sent" if channel == "in_app" else "queued",
                        destination_kind="offer",
                        destination_id=offer.id,
                    )
                )
        subscription.status = "notified"
        subscription.notified_at = subscription.notified_at or now
        add_outbox_event(
            session,
            DomainEvent(
                event_type="catalog.offer_available",
                aggregate_type="offer",
                aggregate_id=str(offer.id),
                payload={
                    "offer_id": str(offer.id),
                    "subscription_id": str(subscription.id),
                    "identity_id": str(subscription.identity_id),
                    "order_created": False,
                },
            ),
        )
        sent += 1
    return sent
