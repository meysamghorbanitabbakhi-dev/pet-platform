from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.time import utc_now
from app.modules.catalog.models import Offer
from app.modules.checkout.service import CheckoutError, CheckoutItem, CheckoutService
from app.modules.food_estimation.models import FoodEstimate
from app.modules.inventory.models import InventoryUnit
from app.modules.orders.models import Order
from app.modules.replenishment.models import (
    ReplenishmentReservation,
    ReplenishmentReservationEvent,
)
from app.modules.system.outbox import DomainEvent, add_outbox_event

_DEFAULT_LEAD_DAYS = 14
_DEFAULT_APPROVAL_WINDOW_HOURS = 48


class ReplenishmentReservationError(Exception):
    pass


def _event(
    reservation_id: UUID,
    event_type: str,
    occurred_at: datetime,
    *,
    identity_id: UUID | None = None,
    reason: str | None = None,
) -> ReplenishmentReservationEvent:
    return ReplenishmentReservationEvent(
        reservation_id=reservation_id,
        event_type=event_type,
        occurred_at=occurred_at,
        reason=reason,
        identity_id=identity_id,
    )


async def _find_available_offer(session: AsyncSession, *, product_id: UUID) -> Offer | None:
    """Same 'reorderable' definition as _reorder_options in pet_life.py
    (status=active, stock_posture=sourced_after_payment,
    sourcing_capacity_status=open) -- deliberately not a second,
    subtly-different notion of availability."""
    offer = await session.scalar(
        select(Offer)
        .where(
            Offer.product_id == product_id,
            Offer.status == "active",
            Offer.stock_posture == "sourced_after_payment",
            Offer.sourcing_capacity_status == "open",
        )
        .order_by(Offer.created_at, Offer.id)
        .limit(1)
    )
    return offer


async def create_or_refresh_reservation_for_unit(
    session: AsyncSession,
    *,
    unit: InventoryUnit,
    lead_days: int = _DEFAULT_LEAD_DAYS,
    approval_window_hours: int = _DEFAULT_APPROVAL_WINDOW_HOURS,
) -> ReplenishmentReservation | None:
    """Create (or, if one is already pending_approval, refresh in place)
    the single reservation for this unit's depletion cycle. Returns None
    when there is nothing to do: no active estimate, an unestimatable
    (unknown-share) estimate, the pessimistic depletion is not yet within
    `lead_days`, or no reorderable offer currently exists for the
    product -- "do not create without sufficient facts" is enforced by
    simply having nothing to act on, not a separate check.

    Caller must have already row-locked `unit` (with_for_update) so this
    and a concurrent correct/exhaust of the same unit serialize
    correctly.
    """
    if unit.state != "opened" or unit.product_id is None:
        return None
    estimate = await session.scalar(
        select(FoodEstimate)
        .where(FoodEstimate.inventory_unit_id == unit.id, FoodEstimate.status == "active")
        .order_by(FoodEstimate.calculated_at.desc())
        .limit(1)
    )
    if estimate is None or estimate.low_days is None or estimate.high_days is None:
        return None
    if estimate.low_days > lead_days:
        return None

    existing = await session.scalar(
        select(ReplenishmentReservation).where(
            ReplenishmentReservation.inventory_unit_id == unit.id
        )
    )
    now = utc_now()
    if existing is not None:
        if existing.status != "pending_approval":
            return existing
        if (
            existing.source_food_estimate_id == estimate.id
            and existing.predicted_depletion_low_days == estimate.low_days
            and existing.predicted_depletion_high_days == estimate.high_days
        ):
            return existing
        existing.source_food_estimate_id = estimate.id
        existing.predicted_depletion_low_days = estimate.low_days
        existing.predicted_depletion_high_days = estimate.high_days
        session.add(_event(existing.id, "refreshed", now))
        await session.flush()
        return existing

    offer = await _find_available_offer(session, product_id=unit.product_id)
    if offer is None:
        return None

    reservation = ReplenishmentReservation(
        household_id=unit.household_id,
        pet_id=estimate.pet_id,
        inventory_unit_id=unit.id,
        product_id=unit.product_id,
        offer_id=offer.id,
        quantity=1,
        source_food_estimate_id=estimate.id,
        predicted_depletion_low_days=estimate.low_days,
        predicted_depletion_high_days=estimate.high_days,
        idempotency_key=f"replenishment:{unit.id}",
        status="pending_approval",
        approval_expires_at=now + timedelta(hours=approval_window_hours),
    )
    session.add(reservation)
    await session.flush()
    session.add(_event(reservation.id, "created", now))
    add_outbox_event(
        session,
        DomainEvent(
            event_type="replenishment.reservation_created",
            aggregate_type="replenishment_reservation",
            aggregate_id=str(reservation.id),
            payload={
                "replenishment_reservation_id": str(reservation.id),
                "household_id": str(reservation.household_id),
                "predicted_depletion_low_days": estimate.low_days,
                "approval_expires_at": reservation.approval_expires_at.isoformat(),
            },
        ),
    )
    return reservation


def _expire_if_past_deadline(reservation: ReplenishmentReservation, now: datetime) -> bool:
    if reservation.status != "pending_approval" or now <= reservation.approval_expires_at:
        return False
    reservation.status = "expired"
    reservation.expired_at = now
    return True


async def approve_reservation(
    session: AsyncSession,
    *,
    reservation: ReplenishmentReservation,
    customer_identity_id: UUID,
    address_id: UUID,
) -> tuple[ReplenishmentReservation, Order]:
    """Approval creates a real, full-payment Order via the existing
    CheckoutService at whatever the live offer price is -- there is no
    reconfirmed-price concept for this workstream, unlike Workstream 2C's
    reserve-now. No auto-charge: the customer must still explicitly pay
    through PaymentService from here, same as any other checkout.
    Idempotent: approving an already-approved reservation returns the
    same order. Caller must have already row-locked `reservation`.
    """
    if reservation.status == "approved":
        if reservation.resulting_order_id is None:
            raise ReplenishmentReservationError("approved_reservation_missing_order")
        order = await session.get(Order, reservation.resulting_order_id)
        if order is None:
            raise ReplenishmentReservationError("approved_reservation_missing_order")
        return reservation, order
    if reservation.status != "pending_approval":
        raise ReplenishmentReservationError(
            f"reservation_not_open_for_response:{reservation.status}"
        )
    now = utc_now()
    if _expire_if_past_deadline(reservation, now):
        session.add(_event(reservation.id, "expired", now))
        await session.commit()
        raise ReplenishmentReservationError("reservation_response_window_expired")
    try:
        order = await CheckoutService().create_order(
            session,
            customer_identity_id=customer_identity_id,
            household_id=reservation.household_id,
            address_id=address_id,
            items=[CheckoutItem(reservation.offer_id, reservation.quantity)],
            idempotency_key=f"replenishment:{reservation.id}",
        )
    except CheckoutError as exc:
        raise ReplenishmentReservationError(f"checkout_failed:{exc}") from exc
    reservation.status = "approved"
    reservation.approved_at = now
    reservation.resulting_order_id = order.id
    session.add(_event(reservation.id, "approved", now, identity_id=customer_identity_id))
    await session.commit()
    return reservation, order


async def decline_reservation(
    session: AsyncSession,
    *,
    reservation: ReplenishmentReservation,
    customer_identity_id: UUID,
    reason: str | None,
) -> ReplenishmentReservation:
    """Caller must have already row-locked `reservation`."""
    if reservation.status == "declined":
        return reservation
    if reservation.status != "pending_approval":
        raise ReplenishmentReservationError(
            f"reservation_not_open_for_response:{reservation.status}"
        )
    now = utc_now()
    if _expire_if_past_deadline(reservation, now):
        session.add(_event(reservation.id, "expired", now))
        await session.flush()
        raise ReplenishmentReservationError("reservation_response_window_expired")
    reservation.status = "declined"
    reservation.declined_at = now
    session.add(
        _event(reservation.id, "declined", now, identity_id=customer_identity_id, reason=reason)
    )
    await session.flush()
    return reservation


async def invalidate_reservation_for_unit(
    session: AsyncSession, *, inventory_unit_id: UUID, reason: str
) -> ReplenishmentReservation | None:
    """Corrected/exhausted units invalidate a still-pending reservation --
    an already-approved one (a real order exists) is never retroactively
    invalidated by a later correction/exhaustion. Called from within
    correct_estimate/exhaust_inventory's own transaction; does not
    commit."""
    reservation = await session.scalar(
        select(ReplenishmentReservation)
        .where(ReplenishmentReservation.inventory_unit_id == inventory_unit_id)
        .with_for_update()
    )
    if reservation is None or reservation.status != "pending_approval":
        return reservation
    now = utc_now()
    reservation.status = "invalidated"
    reservation.invalidated_at = now
    session.add(_event(reservation.id, "invalidated", now, reason=reason))
    return reservation


async def expire_stale_reservations(
    session_factory: async_sessionmaker[AsyncSession], *, batch_size: int = 100
) -> int:
    """Scheduler sweep: a pending_approval reservation past its deadline
    expires, and gets exactly one final reminder notification -- 'On
    expiry, send one final reminder and stop.'"""
    now = utc_now()
    expired = 0
    async with session_factory() as session:
        reservations = list(
            (
                await session.scalars(
                    select(ReplenishmentReservation)
                    .where(
                        ReplenishmentReservation.status == "pending_approval",
                        ReplenishmentReservation.approval_expires_at < now,
                    )
                    .order_by(ReplenishmentReservation.approval_expires_at)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for reservation in reservations:
            if not _expire_if_past_deadline(reservation, now):
                continue
            reservation.reminder_sent_at = now
            session.add(_event(reservation.id, "expired", now))
            add_outbox_event(
                session,
                DomainEvent(
                    event_type="replenishment.reservation_expired",
                    aggregate_type="replenishment_reservation",
                    aggregate_id=str(reservation.id),
                    payload={
                        "replenishment_reservation_id": str(reservation.id),
                        "household_id": str(reservation.household_id),
                    },
                ),
            )
            expired += 1
        await session.commit()
    return expired


async def scan_and_create_due_reservations(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    lead_days: int = _DEFAULT_LEAD_DAYS,
    approval_window_hours: int = _DEFAULT_APPROVAL_WINDOW_HOURS,
    batch_size: int = 100,
) -> dict[str, int]:
    """Scheduler entry point: scan opened inventory units whose pessimistic
    depletion estimate is within `lead_days` and create or refresh their
    reservation. Units without a computable estimate or without any
    currently reorderable offer are silently skipped, not fabricated."""
    counts = {"created": 0, "refreshed": 0}
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(InventoryUnit.id)
                .join(FoodEstimate, FoodEstimate.inventory_unit_id == InventoryUnit.id)
                .where(
                    InventoryUnit.state == "opened",
                    InventoryUnit.product_id.is_not(None),
                    FoodEstimate.status == "active",
                    FoodEstimate.low_days.is_not(None),
                    FoodEstimate.low_days <= lead_days,
                )
                .order_by(InventoryUnit.id)
                .limit(batch_size)
            )
        ).all()
        unit_ids = [row[0] for row in rows]
        for unit_id in unit_ids:
            unit = await session.scalar(
                select(InventoryUnit).where(InventoryUnit.id == unit_id).with_for_update()
            )
            if unit is None:
                continue
            existing = await session.scalar(
                select(ReplenishmentReservation.status).where(
                    ReplenishmentReservation.inventory_unit_id == unit_id
                )
            )
            result = await create_or_refresh_reservation_for_unit(
                session,
                unit=unit,
                lead_days=lead_days,
                approval_window_hours=approval_window_hours,
            )
            if result is None:
                continue
            if existing is None:
                counts["created"] += 1
            elif existing == "pending_approval":
                counts["refreshed"] += 1
        await session.commit()
    return counts
