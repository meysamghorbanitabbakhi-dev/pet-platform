from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.time import utc_now
from app.modules.catalog.models import Offer, Supplier
from app.modules.households.models import HouseholdAddress
from app.modules.orders.models import Order, OrderLine
from app.modules.reservations.models import Reservation, ReservationEvent
from app.modules.system.outbox import DomainEvent, add_outbox_event

_DEFAULT_OPERATOR_REVIEW_WINDOW_HOURS = 48
_DEFAULT_CUSTOMER_RESPONSE_WINDOW_HOURS = 48


class ReservationError(Exception):
    pass


def _event(
    reservation_id: UUID,
    event_type: str,
    occurred_at: datetime,
    *,
    operator_id: UUID | None = None,
    customer_id: UUID | None = None,
    reason: str | None = None,
) -> ReservationEvent:
    return ReservationEvent(
        reservation_id=reservation_id,
        event_type=event_type,
        occurred_at=occurred_at,
        reason=reason,
        operator_identity_id=operator_id,
        customer_identity_id=customer_id,
    )


async def request_reservation(
    session: AsyncSession,
    *,
    offer: Offer,
    customer_identity_id: UUID,
    household_id: UUID,
    quantity: int,
    idempotency_key: str,
    review_window_hours: int = _DEFAULT_OPERATOR_REVIEW_WINDOW_HOURS,
) -> Reservation:
    """Zero-charge reservation request. Idempotent/replay-safe on
    (customer_identity_id, idempotency_key), same pattern as
    CheckoutService.create_order."""
    if offer.mode != "reserve":
        raise ReservationError("offer_is_not_reservable")
    if offer.status != "active" or offer.sourcing_capacity_status != "open":
        raise ReservationError("offer_unavailable")
    now = utc_now()
    if offer.available_from is not None and now < offer.available_from:
        raise ReservationError("offer_unavailable")
    if offer.available_until is not None and now >= offer.available_until:
        raise ReservationError("offer_unavailable")

    existing = await session.scalar(
        select(Reservation).where(
            Reservation.customer_identity_id == customer_identity_id,
            Reservation.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing

    reservation = Reservation(
        customer_identity_id=customer_identity_id,
        household_id=household_id,
        offer_id=offer.id,
        quantity=quantity,
        requested_price_irr=offer.price_irr,
        requested_at=now,
        idempotency_key=idempotency_key,
        operator_review_by=now + timedelta(hours=review_window_hours),
        status="requested",
    )
    session.add(reservation)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        replay = await session.scalar(
            select(Reservation).where(
                Reservation.customer_identity_id == customer_identity_id,
                Reservation.idempotency_key == idempotency_key,
            )
        )
        if replay is not None:
            return replay
        raise ReservationError("idempotency_key_conflict") from exc
    session.add(_event(reservation.id, "requested", now, customer_id=customer_identity_id))
    await session.flush()
    return reservation


def _expire_if_past_review_deadline(reservation: Reservation, now: datetime) -> bool:
    if reservation.status != "requested" or now <= reservation.operator_review_by:
        return False
    reservation.status = "expired"
    return True


def _expire_if_past_response_deadline(reservation: Reservation, now: datetime) -> bool:
    if (
        reservation.status != "proposed"
        or reservation.customer_respond_by is None
        or now <= reservation.customer_respond_by
    ):
        return False
    reservation.status = "expired"
    reservation.responded_at = now
    return True


async def reconfirm_and_propose_reservation(
    session: AsyncSession,
    *,
    reservation: Reservation,
    operator_id: UUID,
    reconfirmed_price_irr: int,
    reconfirmed_available: bool,
    reason: str,
    response_window_hours: int = _DEFAULT_CUSTOMER_RESPONSE_WINDOW_HOURS,
) -> Reservation:
    """Operator source/price reconfirmation, proposed to the customer for
    explicit approval or decline. Caller must have already row-locked
    `reservation` (with_for_update)."""
    if reservation.status == "proposed":
        return reservation
    if reservation.status != "requested":
        raise ReservationError(f"reservation_not_open_for_review:{reservation.status}")
    now = utc_now()
    if _expire_if_past_review_deadline(reservation, now):
        session.add(_event(reservation.id, "expired", now))
        await session.flush()
        raise ReservationError("reservation_review_window_expired")
    reservation.reconfirmed_price_irr = reconfirmed_price_irr
    reservation.reconfirmed_available = reconfirmed_available
    reservation.proposed_at = now
    reservation.proposed_by_operator_id = operator_id
    reservation.proposal_reason = reason
    reservation.customer_respond_by = now + timedelta(hours=response_window_hours)
    reservation.status = "proposed"
    session.add(_event(reservation.id, "proposed", now, operator_id=operator_id, reason=reason))
    add_outbox_event(
        session,
        DomainEvent(
            event_type="reservations.proposed",
            aggregate_type="reservation",
            aggregate_id=str(reservation.id),
            payload={
                "reservation_id": str(reservation.id),
                "household_id": str(reservation.household_id),
                "reconfirmed_price_irr": reconfirmed_price_irr,
                "customer_respond_by": reservation.customer_respond_by.isoformat(),
            },
        ),
    )
    await session.flush()
    return reservation


async def operator_decline_reservation(
    session: AsyncSession, *, reservation: Reservation, operator_id: UUID, reason: str
) -> Reservation:
    """The operator determines the offer cannot be sourced at all for this
    reservation -- skips proposing anything to the customer. Caller must
    have already row-locked `reservation`."""
    if reservation.status == "operator_declined":
        return reservation
    if reservation.status not in ("requested", "proposed"):
        raise ReservationError(f"reservation_not_declinable:{reservation.status}")
    now = utc_now()
    reservation.status = "operator_declined"
    reservation.decline_reason = reason
    session.add(
        _event(
            reservation.id, "operator_declined", now, operator_id=operator_id, reason=reason
        )
    )
    await session.flush()
    return reservation


async def decline_reservation(
    session: AsyncSession,
    *,
    reservation: Reservation,
    customer_identity_id: UUID,
    reason: str | None,
) -> Reservation:
    """Customer declines the operator-proposed terms. Caller must have
    already row-locked `reservation`."""
    if reservation.status == "customer_declined":
        return reservation
    if reservation.status != "proposed":
        raise ReservationError(f"reservation_not_open_for_response:{reservation.status}")
    now = utc_now()
    if _expire_if_past_response_deadline(reservation, now):
        session.add(_event(reservation.id, "expired", now))
        await session.flush()
        raise ReservationError("reservation_response_window_expired")
    reservation.status = "customer_declined"
    reservation.responded_at = now
    reservation.decline_reason = reason
    session.add(
        _event(
            reservation.id,
            "customer_declined",
            now,
            customer_id=customer_identity_id,
            reason=reason,
        )
    )
    await session.flush()
    return reservation


async def approve_and_convert_reservation(
    session: AsyncSession,
    *,
    reservation: Reservation,
    offer: Offer,
    supplier: Supplier,
    address: HouseholdAddress,
    customer_identity_id: UUID,
) -> tuple[Reservation, Order]:
    """Customer approves the reconfirmed terms: creates a real,
    full-payment Order at the reconfirmed price (never the live
    offer.price_irr at whatever moment this happens to run) and returns
    it for the caller to proceed through the existing PaymentService
    flow. Idempotent: approving an already-converted reservation returns
    the same order. Caller must have already row-locked `reservation`.
    """
    if reservation.status == "converted":
        if reservation.order_id is None:
            raise ReservationError("converted_reservation_missing_order")
        order = await session.get(Order, reservation.order_id)
        if order is None:
            raise ReservationError("converted_reservation_missing_order")
        return reservation, order
    if reservation.status != "proposed":
        raise ReservationError(f"reservation_not_open_for_response:{reservation.status}")
    now = utc_now()
    if _expire_if_past_response_deadline(reservation, now):
        session.add(_event(reservation.id, "expired", now))
        await session.flush()
        raise ReservationError("reservation_response_window_expired")
    if address.household_id != reservation.household_id or not address.active:
        raise ReservationError("delivery_address_unavailable")
    if reservation.reconfirmed_price_irr is None:
        raise ReservationError("reservation_missing_reconfirmed_price")

    line_total = reservation.reconfirmed_price_irr * reservation.quantity
    delivery_snapshot: dict[str, Any] = {
        "address_id": str(address.id),
        "label": address.label,
        "recipient_name": address.recipient_name,
        "recipient_mobile_e164": address.recipient_mobile_e164,
        "province": address.province,
        "city": address.city,
        "address_line": address.address_line,
        "postal_code": address.postal_code,
    }
    order = Order(
        customer_identity_id=customer_identity_id,
        household_id=reservation.household_id,
        status="awaiting_payment",
        currency="IRR",
        merchandise_total_irr=line_total,
        checkout_idempotency_key=f"reservation:{reservation.id}",
        delivery_address_snapshot=delivery_snapshot,
    )
    session.add(order)
    await session.flush()
    session.add(
        OrderLine(
            order_id=order.id,
            offer_id=offer.id,
            sku_snapshot=offer.sku,
            title_fa_snapshot=offer.title_fa,
            unit_label_fa_snapshot=offer.unit_label_fa,
            supplier_country_snapshot=supplier.country_code,
            quantity=reservation.quantity,
            unit_price_irr=reservation.reconfirmed_price_irr,
            line_total_irr=line_total,
            created_at=now,
        )
    )
    reservation.status = "converted"
    reservation.responded_at = now
    reservation.order_id = order.id
    reservation.converted_at = now
    add_outbox_event(
        session,
        DomainEvent(
            event_type="order.awaiting_payment",
            aggregate_type="order",
            aggregate_id=str(order.id),
            payload={"order_id": str(order.id), "amount_irr": line_total, "currency": "IRR"},
        ),
    )
    session.add(
        _event(reservation.id, "approved", now, customer_id=customer_identity_id)
    )
    session.add(
        _event(reservation.id, "converted", now, customer_id=customer_identity_id)
    )
    await session.flush()
    return reservation, order


async def expire_stale_reservations(
    session_factory: async_sessionmaker[AsyncSession], *, batch_size: int = 100
) -> dict[str, int]:
    """Scheduler sweep covering both deadlines: a 'requested' reservation
    the operator never reviewed, and a 'proposed' one the customer never
    answered. Runs unconditionally -- this module is only ever reachable
    when settings.reserve_now_enabled is True, so once live there is no
    separate flag gating the sweep itself.
    """
    now = utc_now()
    counts = {"review_expired": 0, "response_expired": 0}
    async with session_factory() as session:
        requested = list(
            (
                await session.scalars(
                    select(Reservation)
                    .where(
                        Reservation.status == "requested",
                        Reservation.operator_review_by < now,
                    )
                    .order_by(Reservation.operator_review_by)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for reservation in requested:
            if _expire_if_past_review_deadline(reservation, now):
                session.add(_event(reservation.id, "expired", now))
                counts["review_expired"] += 1
        await session.commit()

    async with session_factory() as session:
        proposed = list(
            (
                await session.scalars(
                    select(Reservation)
                    .where(
                        Reservation.status == "proposed",
                        Reservation.customer_respond_by < now,
                    )
                    .order_by(Reservation.customer_respond_by)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for reservation in proposed:
            if _expire_if_past_response_deadline(reservation, now):
                session.add(_event(reservation.id, "expired", now))
                counts["response_expired"] += 1
        await session.commit()

    return counts
