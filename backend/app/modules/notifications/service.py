from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.time import utc_now
from app.integrations.notifications.port import SmsProvider
from app.modules.households.models import HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.notifications.models import (
    Notification,
    NotificationAttempt,
    NotificationPreference,
    NotificationTemplate,
)

IRAN_TZ = ZoneInfo("Asia/Tehran")


async def enqueue_wallet_credit_notification(
    session_factory: async_sessionmaker[AsyncSession],
    payload: dict[str, Any],
    *,
    customer_visible: bool,
) -> None:
    if not customer_visible:
        return
    household_id = UUID(str(payload["household_id"]))
    source_id = str(payload["order_id"])
    async with session_factory() as session:
        owner = await session.scalar(
            select(AuthIdentity)
            .join(HouseholdMembership, HouseholdMembership.identity_id == AuthIdentity.id)
            .where(
                HouseholdMembership.household_id == household_id,
                HouseholdMembership.role == "owner",
                AuthIdentity.status == "active",
            )
            .order_by(HouseholdMembership.created_at)
            .limit(1)
        )
        if owner is None:
            raise RuntimeError("wallet credit household has no active owner")
        preference = await session.scalar(
            select(NotificationPreference).where(
                NotificationPreference.identity_id == owner.id,
                NotificationPreference.channel == "sms",
                NotificationPreference.event_key == "wallet.late_delivery_credit_granted",
            )
        )
        for channel in ("in_app", "sms"):
            existing = await session.scalar(
                select(Notification).where(
                    Notification.event_key == "wallet.late_delivery_credit_granted",
                    Notification.source_id == source_id,
                    Notification.recipient_identity_id == owner.id,
                    Notification.channel == channel,
                )
            )
            if existing is not None:
                continue
            status = "sent" if channel == "in_app" else "queued"
            if channel == "sms" and preference is not None and not preference.enabled:
                status = "suppressed"
            session.add(
                Notification(
                    recipient_identity_id=owner.id,
                    event_key="wallet.late_delivery_credit_granted",
                    source_id=source_id,
                    channel=channel,
                    payload=payload,
                    status=status,
                    destination_kind="order",
                    destination_id=UUID(source_id),
                )
            )
        await session.commit()


async def enqueue_shelf_life_exception_notification(
    session_factory: async_sessionmaker[AsyncSession],
    payload: dict[str, Any],
) -> None:
    """Notify the household owner a shelf-life exception needs a response.

    Unlike enqueue_wallet_credit_notification, this is not gated behind a
    customer-visibility settings flag: propose/accept/decline is the
    customer's actual right under Workstream 2E, not an optional
    informational surface, so suppressing the notification would silently
    push every exception toward the expired/declined outcome instead of
    letting the customer choose.
    """
    household_id = UUID(str(payload["household_id"]))
    source_id = str(payload["shelf_life_exception_id"])
    async with session_factory() as session:
        owner = await session.scalar(
            select(AuthIdentity)
            .join(HouseholdMembership, HouseholdMembership.identity_id == AuthIdentity.id)
            .where(
                HouseholdMembership.household_id == household_id,
                HouseholdMembership.role == "owner",
                AuthIdentity.status == "active",
            )
            .order_by(HouseholdMembership.created_at)
            .limit(1)
        )
        if owner is None:
            raise RuntimeError("shelf-life exception household has no active owner")
        preference = await session.scalar(
            select(NotificationPreference).where(
                NotificationPreference.identity_id == owner.id,
                NotificationPreference.channel == "sms",
                NotificationPreference.event_key == "orders.shelf_life_exception_proposed",
            )
        )
        for channel in ("in_app", "sms"):
            existing = await session.scalar(
                select(Notification).where(
                    Notification.event_key == "orders.shelf_life_exception_proposed",
                    Notification.source_id == source_id,
                    Notification.recipient_identity_id == owner.id,
                    Notification.channel == channel,
                )
            )
            if existing is not None:
                continue
            status = "sent" if channel == "in_app" else "queued"
            if channel == "sms" and preference is not None and not preference.enabled:
                status = "suppressed"
            session.add(
                Notification(
                    recipient_identity_id=owner.id,
                    event_key="orders.shelf_life_exception_proposed",
                    source_id=source_id,
                    channel=channel,
                    payload=payload,
                    status=status,
                    destination_kind="order",
                    destination_id=UUID(str(payload["order_id"])),
                )
            )
        await session.commit()


async def enqueue_reservation_notification(
    session_factory: async_sessionmaker[AsyncSession],
    payload: dict[str, Any],
) -> None:
    """Notify the household owner a reservation's reconfirmed terms need a
    response. Not gated behind a visibility flag, same reasoning as
    enqueue_shelf_life_exception_notification -- this is the customer's
    actual approve/decline right, not an optional informational surface.
    """
    household_id = UUID(str(payload["household_id"]))
    source_id = str(payload["reservation_id"])
    async with session_factory() as session:
        owner = await session.scalar(
            select(AuthIdentity)
            .join(HouseholdMembership, HouseholdMembership.identity_id == AuthIdentity.id)
            .where(
                HouseholdMembership.household_id == household_id,
                HouseholdMembership.role == "owner",
                AuthIdentity.status == "active",
            )
            .order_by(HouseholdMembership.created_at)
            .limit(1)
        )
        if owner is None:
            raise RuntimeError("reservation household has no active owner")
        preference = await session.scalar(
            select(NotificationPreference).where(
                NotificationPreference.identity_id == owner.id,
                NotificationPreference.channel == "sms",
                NotificationPreference.event_key == "reservations.proposed",
            )
        )
        for channel in ("in_app", "sms"):
            existing = await session.scalar(
                select(Notification).where(
                    Notification.event_key == "reservations.proposed",
                    Notification.source_id == source_id,
                    Notification.recipient_identity_id == owner.id,
                    Notification.channel == channel,
                )
            )
            if existing is not None:
                continue
            status = "sent" if channel == "in_app" else "queued"
            if channel == "sms" and preference is not None and not preference.enabled:
                status = "suppressed"
            session.add(
                Notification(
                    recipient_identity_id=owner.id,
                    event_key="reservations.proposed",
                    source_id=source_id,
                    channel=channel,
                    payload=payload,
                    status=status,
                    destination_kind="none",
                )
            )
        await session.commit()


async def deliver_pending_sms(
    session_factory: async_sessionmaker[AsyncSession],
    provider: SmsProvider,
    *,
    batch_size: int = 50,
) -> int:
    async with session_factory() as session:
        notifications = list(
            (
                await session.scalars(
                    select(Notification)
                    .where(
                        Notification.channel == "sms",
                        Notification.status.in_(("queued", "deferred")),
                        (Notification.next_attempt_at.is_(None))
                        | (Notification.next_attempt_at <= utc_now()),
                    )
                    .order_by(Notification.created_at)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        sent = 0
        for notification in notifications:
            identity = await session.get(AuthIdentity, notification.recipient_identity_id)
            template = await session.scalar(
                select(NotificationTemplate)
                .where(
                    NotificationTemplate.event_key == notification.event_key,
                    NotificationTemplate.channel == "sms",
                    NotificationTemplate.active.is_(True),
                )
                .order_by(NotificationTemplate.version.desc())
                .limit(1)
            )
            preference = await session.scalar(
                select(NotificationPreference).where(
                    NotificationPreference.identity_id == notification.recipient_identity_id,
                    NotificationPreference.channel == "sms",
                    NotificationPreference.event_key == notification.event_key,
                )
            )
            if identity is None or template is None:
                notification.status = "failed"
                session.add(
                    NotificationAttempt(
                        notification_id=notification.id,
                        status="failed",
                        error_code="recipient_or_template_missing",
                    )
                )
                continue
            if preference is not None and not preference.enabled:
                notification.status = "suppressed"
                continue
            if preference is not None and _inside_quiet_hours(preference, utc_now()):
                notification.status = "deferred"
                notification.next_attempt_at = utc_now() + timedelta(minutes=15)
                continue
            try:
                text = template.body_fa.format_map(_StrictPayload(notification.payload))
                reference = await provider.send_message(
                    mobile_e164=identity.mobile_e164,
                    text=text,
                    correlation_id=str(notification.id),
                )
            except Exception as exc:
                notification.attempt_count += 1
                notification.status = "failed" if notification.attempt_count >= 5 else "queued"
                notification.next_attempt_at = (
                    None
                    if notification.status == "failed"
                    else utc_now() + timedelta(minutes=min(60, 2**notification.attempt_count))
                )
                session.add(
                    NotificationAttempt(
                        notification_id=notification.id,
                        status="failed",
                        error_code=type(exc).__name__,
                    )
                )
            else:
                notification.status = "sent"
                notification.attempt_count += 1
                notification.next_attempt_at = None
                session.add(
                    NotificationAttempt(
                        notification_id=notification.id,
                        status="sent",
                        provider_reference=reference,
                    )
                )
                sent += 1
        await session.commit()
        return sent


def _inside_quiet_hours(preference: NotificationPreference, now: datetime) -> bool:
    start = preference.quiet_start_local
    end = preference.quiet_end_local
    if start is None or end is None or start == end:
        return False
    local_time = now.astimezone(IRAN_TZ).time().replace(tzinfo=None)
    if start < end:
        return start <= local_time < end
    return local_time >= start or local_time < end


class _StrictPayload(dict[str, Any]):
    def __missing__(self, key: str) -> Any:
        raise KeyError(f"notification payload omitted {key}")
