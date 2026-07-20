from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.time import utc_now
from app.modules.catalog.models import Offer, Product, Supplier
from app.modules.checkout.service import CheckoutError, CheckoutItem, CheckoutService
from app.modules.concierge.models import ConciergeOffer, ConciergeOfferEvent
from app.modules.orders.models import Order
from app.modules.support.models import CustomerRequest, CustomerRequestStatusAudit
from app.modules.system.outbox import DomainEvent, add_outbox_event
from app.modules.trust.files import EvidenceFile

_DEFAULT_VALIDITY_HOURS = 24
_ACTIVE_STATUSES = ("reviewing", "offer_presented", "refresh_requested")


class ConciergeOfferError(Exception):
    pass


@dataclass(slots=True)
class OfferPresentationFacts:
    title_fa: str
    unit_label_fa: str
    quantity: int
    authenticity_basis: str
    supplier_id: UUID
    verification_evidence_file_id: UUID
    minimum_shelf_life_months: int
    estimated_delivery_days: int
    pricing_mode: str
    price_irr: int
    price_explanation_fa: str
    reference_price_irr: int | None = None
    supplier_cost_irr: int | None = None
    exchange_rate_basis_irr_per_unit: int | None = None
    international_transport_irr: int | None = None
    customs_clearance_irr: int | None = None
    handling_irr: int | None = None
    domestic_delivery_irr: int | None = None
    payment_fees_irr: int | None = None
    risk_reserve_irr: int | None = None
    platform_margin_irr: int | None = None
    validity_hours: int = _DEFAULT_VALIDITY_HOURS


def _event(
    offer_id: UUID,
    event_type: str,
    occurred_at: datetime,
    *,
    operator_id: UUID | None = None,
    customer_id: UUID | None = None,
    reason: str | None = None,
) -> ConciergeOfferEvent:
    return ConciergeOfferEvent(
        offer_id=offer_id,
        event_type=event_type,
        occurred_at=occurred_at,
        reason=reason,
        operator_identity_id=operator_id,
        customer_identity_id=customer_id,
    )


async def _resolve_request(
    session: AsyncSession,
    request_id: UUID,
    *,
    operator_id: UUID | None,
    now: datetime,
    note: str,
) -> None:
    request = await session.get(CustomerRequest, request_id)
    if request is None or request.status == "resolved":
        return
    before = request.status
    request.status = "resolved"
    session.add(
        CustomerRequestStatusAudit(
            request_id=request.id,
            operator_identity_id=operator_id,
            old_status=before,
            new_status="resolved",
            reason=note,
            facts={},
            changed_at=now,
        )
    )


async def start_review(
    session: AsyncSession, *, request: CustomerRequest, operator_id: UUID
) -> ConciergeOffer:
    """Operator picks up a concierge_sourcing request -- fresh, or a
    customer-initiated refresh -- and begins verification. Idempotent: an
    already-reviewing/offer_presented cycle is returned unchanged; a
    refresh_requested cycle advances to reviewing. Caller must have
    already row-locked the active ConciergeOffer if one is known, or rely
    on the row lock this function itself takes when searching for one.
    """
    if request.request_type != "concierge_sourcing":
        raise ConciergeOfferError("request_is_not_concierge_sourcing")
    active = await session.scalar(
        select(ConciergeOffer)
        .where(
            ConciergeOffer.request_id == request.id,
            ConciergeOffer.status.in_(_ACTIVE_STATUSES),
        )
        .order_by(ConciergeOffer.created_at.desc())
        .with_for_update()
    )
    now = utc_now()
    if active is not None:
        if active.status in ("reviewing", "offer_presented"):
            return active
        active.status = "reviewing"
        active.reviewing_started_at = now
        active.reviewing_started_by_operator_id = operator_id
        session.add(_event(active.id, "reviewing_started", now, operator_id=operator_id))
        await session.flush()
        return active
    offer = ConciergeOffer(
        request_id=request.id,
        household_id=request.household_id,
        customer_identity_id=request.identity_id,
        status="reviewing",
        reviewing_started_at=now,
        reviewing_started_by_operator_id=operator_id,
    )
    session.add(offer)
    await session.flush()
    session.add(_event(offer.id, "reviewing_started", now, operator_id=operator_id))
    if request.status == "submitted":
        before = request.status
        request.status = "in_review"
        session.add(
            CustomerRequestStatusAudit(
                request_id=request.id,
                operator_identity_id=operator_id,
                old_status=before,
                new_status="in_review",
                reason="concierge offer review started",
                facts={},
                changed_at=now,
            )
        )
    await session.flush()
    return offer


async def present_offer(
    session: AsyncSession,
    *,
    offer: ConciergeOffer,
    operator_id: UUID,
    facts: OfferPresentationFacts,
) -> ConciergeOffer:
    """Operator presents a verified, payable offer (Decision 0.33/0.34).
    Caller must have already row-locked `offer`."""
    if offer.status == "offer_presented":
        return offer
    if offer.status != "reviewing":
        raise ConciergeOfferError(f"offer_not_open_for_presentation:{offer.status}")
    if not (12 <= facts.validity_hours <= 48):
        raise ConciergeOfferError("validity_hours_out_of_range")
    if facts.pricing_mode == "reference_price_savings":
        if facts.reference_price_irr is None:
            raise ConciergeOfferError("reference_price_required")
    elif facts.pricing_mode == "landed_cost_plus_margin":
        if facts.supplier_cost_irr is None or facts.platform_margin_irr is None:
            raise ConciergeOfferError("landed_cost_components_required")
    else:
        raise ConciergeOfferError("invalid_pricing_mode")
    supplier = await session.get(Supplier, facts.supplier_id)
    if supplier is None:
        raise ConciergeOfferError("supplier_not_found")
    evidence = await session.get(EvidenceFile, facts.verification_evidence_file_id)
    if evidence is None:
        raise ConciergeOfferError("verification_evidence_not_found")

    now = utc_now()
    offer.title_fa = facts.title_fa
    offer.unit_label_fa = facts.unit_label_fa
    offer.quantity = facts.quantity
    offer.authenticity_basis = facts.authenticity_basis
    offer.supplier_id = facts.supplier_id
    offer.verification_evidence_file_id = facts.verification_evidence_file_id
    offer.minimum_shelf_life_months = facts.minimum_shelf_life_months
    offer.estimated_delivery_days = facts.estimated_delivery_days
    offer.pricing_mode = facts.pricing_mode
    offer.price_irr = facts.price_irr
    offer.reference_price_irr = facts.reference_price_irr
    offer.price_explanation_fa = facts.price_explanation_fa
    offer.supplier_cost_irr = facts.supplier_cost_irr
    offer.exchange_rate_basis_irr_per_unit = facts.exchange_rate_basis_irr_per_unit
    offer.international_transport_irr = facts.international_transport_irr
    offer.customs_clearance_irr = facts.customs_clearance_irr
    offer.handling_irr = facts.handling_irr
    offer.domestic_delivery_irr = facts.domestic_delivery_irr
    offer.payment_fees_irr = facts.payment_fees_irr
    offer.risk_reserve_irr = facts.risk_reserve_irr
    offer.platform_margin_irr = facts.platform_margin_irr
    offer.presented_at = now
    offer.presented_by_operator_id = operator_id
    offer.validity_hours = facts.validity_hours
    offer.expires_at = now + timedelta(hours=facts.validity_hours)
    offer.status = "offer_presented"
    session.add(_event(offer.id, "offer_presented", now, operator_id=operator_id))
    add_outbox_event(
        session,
        DomainEvent(
            event_type="concierge.offer_presented",
            aggregate_type="concierge_offer",
            aggregate_id=str(offer.id),
            payload={
                "concierge_offer_id": str(offer.id),
                "request_id": str(offer.request_id),
                "household_id": str(offer.household_id),
                "expires_at": offer.expires_at.isoformat(),
            },
        ),
    )
    await session.flush()
    return offer


async def mark_unavailable(
    session: AsyncSession, *, offer: ConciergeOffer, operator_id: UUID, reason: str
) -> ConciergeOffer:
    """Operator determines the request cannot be sourced at all, skipping
    the customer entirely -- mirrors reserve-now's operator_declined.
    Caller must have already row-locked `offer`."""
    if offer.status == "unavailable":
        return offer
    if offer.status != "reviewing":
        raise ConciergeOfferError(f"offer_not_open_for_unavailable:{offer.status}")
    now = utc_now()
    offer.status = "unavailable"
    offer.unavailable_reason = reason
    offer.unavailable_by_operator_id = operator_id
    session.add(
        _event(offer.id, "marked_unavailable", now, operator_id=operator_id, reason=reason)
    )
    add_outbox_event(
        session,
        DomainEvent(
            event_type="concierge.offer_unavailable",
            aggregate_type="concierge_offer",
            aggregate_id=str(offer.id),
            payload={
                "concierge_offer_id": str(offer.id),
                "request_id": str(offer.request_id),
                "household_id": str(offer.household_id),
                "reason": reason,
            },
        ),
    )
    await _resolve_request(
        session,
        offer.request_id,
        operator_id=operator_id,
        now=now,
        note="concierge offer marked unavailable",
    )
    await session.flush()
    return offer


def _expire_if_past_deadline(offer: ConciergeOffer, now: datetime) -> bool:
    if offer.status != "offer_presented" or offer.expires_at is None or now <= offer.expires_at:
        return False
    offer.status = "expired"
    return True


async def accept_offer(
    session: AsyncSession,
    *,
    offer: ConciergeOffer,
    customer_identity_id: UUID,
    address_id: UUID,
) -> tuple[ConciergeOffer, Order]:
    """Accept creates a real, full-payment Order at the price presented
    (locked for the validity window, Decision 0.35) via a one-off
    Product/Offer(mode='concierge_only') pair created lazily here --
    hidden from catalog browse/search until a deliberate operator
    promotion (see promote_to_catalog). No deposit, no auto-charge: the
    customer still pays through the existing PaymentService flow from
    here. Idempotent: accepting an already-accepted offer returns the
    same order. Caller must have already row-locked `offer`.
    """
    if offer.status == "accepted":
        if offer.resulting_order_id is None:
            raise ConciergeOfferError("accepted_offer_missing_order")
        order = await session.get(Order, offer.resulting_order_id)
        if order is None:
            raise ConciergeOfferError("accepted_offer_missing_order")
        return offer, order
    if offer.status != "offer_presented":
        raise ConciergeOfferError(f"offer_not_open_for_response:{offer.status}")
    now = utc_now()
    if _expire_if_past_deadline(offer, now):
        session.add(_event(offer.id, "expired", now))
        await _resolve_request(
            session, offer.request_id, operator_id=None, now=now, note="concierge offer expired"
        )
        await session.commit()
        raise ConciergeOfferError("offer_validity_expired")
    if (
        offer.supplier_id is None
        or offer.title_fa is None
        or offer.price_irr is None
        or offer.minimum_shelf_life_months is None
    ):
        raise ConciergeOfferError("offer_missing_presentation_facts")

    product = Product(name_fa=offer.title_fa, status="active")
    session.add(product)
    await session.flush()
    catalog_offer = Offer(
        product_id=product.id,
        supplier_id=offer.supplier_id,
        sku=f"CONCIERGE-{offer.id}",
        title_fa=offer.title_fa,
        unit_label_fa=offer.unit_label_fa or "عدد",
        price_irr=offer.price_irr,
        status="active",
        stock_posture="sourced_after_payment",
        sourcing_capacity_status="open",
        minimum_shelf_life_months=offer.minimum_shelf_life_months,
        mode="concierge_only",
        sourcing_route="individual",
        max_pending_quantity=offer.quantity,
    )
    session.add(catalog_offer)
    await session.flush()
    try:
        order = await CheckoutService().create_order(
            session,
            customer_identity_id=customer_identity_id,
            household_id=offer.household_id,
            address_id=address_id,
            items=[CheckoutItem(catalog_offer.id, offer.quantity)],
            idempotency_key=f"concierge:{offer.id}",
        )
    except CheckoutError as exc:
        raise ConciergeOfferError(f"checkout_failed:{exc}") from exc
    offer.status = "accepted"
    offer.responded_at = now
    offer.responded_by_customer_identity_id = customer_identity_id
    offer.promoted_offer_id = catalog_offer.id
    offer.resulting_order_id = order.id
    session.add(_event(offer.id, "accepted", now, customer_id=customer_identity_id))
    await _resolve_request(
        session, offer.request_id, operator_id=None, now=now, note="concierge offer accepted"
    )
    await session.commit()
    return offer, order


async def decline_offer(
    session: AsyncSession,
    *,
    offer: ConciergeOffer,
    customer_identity_id: UUID,
    reason: str | None,
) -> ConciergeOffer:
    """Caller must have already row-locked `offer`."""
    if offer.status == "declined":
        return offer
    if offer.status != "offer_presented":
        raise ConciergeOfferError(f"offer_not_open_for_response:{offer.status}")
    now = utc_now()
    if _expire_if_past_deadline(offer, now):
        session.add(_event(offer.id, "expired", now))
        await _resolve_request(
            session, offer.request_id, operator_id=None, now=now, note="concierge offer expired"
        )
        await session.flush()
        raise ConciergeOfferError("offer_validity_expired")
    offer.status = "declined"
    offer.responded_at = now
    offer.responded_by_customer_identity_id = customer_identity_id
    offer.decline_reason = reason
    session.add(
        _event(offer.id, "declined", now, customer_id=customer_identity_id, reason=reason)
    )
    await _resolve_request(
        session, offer.request_id, operator_id=None, now=now, note="concierge offer declined"
    )
    await session.flush()
    return offer


async def request_refresh(
    session: AsyncSession, *, expired_offer: ConciergeOffer, customer_identity_id: UUID
) -> ConciergeOffer:
    """Customer asks for a fresh look after an offer expired (Decision
    0.36) -- creates a new cycle, never reactivates the expired row:
    `expired_offer`'s own fields are never touched again. Idempotent: a
    request while another cycle is already active for the same underlying
    CustomerRequest returns that cycle unchanged rather than creating a
    second one. Caller must have already row-locked `expired_offer`.
    """
    if expired_offer.status != "expired":
        raise ConciergeOfferError(f"offer_not_expired:{expired_offer.status}")
    active = await session.scalar(
        select(ConciergeOffer).where(
            ConciergeOffer.request_id == expired_offer.request_id,
            ConciergeOffer.status.in_(_ACTIVE_STATUSES),
        )
    )
    if active is not None:
        return active
    now = utc_now()
    refreshed = ConciergeOffer(
        request_id=expired_offer.request_id,
        household_id=expired_offer.household_id,
        customer_identity_id=customer_identity_id,
        refreshed_from_offer_id=expired_offer.id,
        status="refresh_requested",
    )
    session.add(refreshed)
    await session.flush()
    session.add(_event(refreshed.id, "refresh_requested", now, customer_id=customer_identity_id))
    session.add(
        _event(
            expired_offer.id,
            "refresh_requested",
            now,
            customer_id=customer_identity_id,
            reason=f"refreshed_as:{refreshed.id}",
        )
    )
    request = await session.get(CustomerRequest, expired_offer.request_id)
    if request is not None and request.status != "submitted":
        before = request.status
        request.status = "submitted"
        session.add(
            CustomerRequestStatusAudit(
                request_id=request.id,
                operator_identity_id=None,
                old_status=before,
                new_status="submitted",
                reason="customer requested a refreshed concierge offer",
                facts={},
                changed_at=now,
            )
        )
    await session.flush()
    return refreshed


async def expire_stale_offers(
    session_factory: async_sessionmaker[AsyncSession], *, batch_size: int = 100
) -> int:
    """Scheduler sweep: an offer_presented row past its validity window
    expires. No automatic re-verification or re-sourcing happens here
    (Decision 0.36) -- the customer must explicitly request a refresh."""
    now = utc_now()
    expired = 0
    async with session_factory() as session:
        offers = list(
            (
                await session.scalars(
                    select(ConciergeOffer)
                    .where(
                        ConciergeOffer.status == "offer_presented",
                        ConciergeOffer.expires_at < now,
                    )
                    .order_by(ConciergeOffer.expires_at)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for offer in offers:
            if not _expire_if_past_deadline(offer, now):
                continue
            session.add(_event(offer.id, "expired", now))
            add_outbox_event(
                session,
                DomainEvent(
                    event_type="concierge.offer_expired",
                    aggregate_type="concierge_offer",
                    aggregate_id=str(offer.id),
                    payload={
                        "concierge_offer_id": str(offer.id),
                        "request_id": str(offer.request_id),
                        "household_id": str(offer.household_id),
                    },
                ),
            )
            await _resolve_request(
                session,
                offer.request_id,
                operator_id=None,
                now=now,
                note="concierge offer expired",
            )
            expired += 1
        await session.commit()
    return expired


async def promote_to_catalog(
    session: AsyncSession, *, offer: ConciergeOffer, operator_id: UUID, rationale: str
) -> Offer:
    """Operator-discretion catalog promotion (Decision 0.37) -- the
    criteria (request frequency, conversion, repeat demand, source
    stability, authenticity confidence, landed margin, delivery
    performance, product documentation, customer feedback, operational
    complexity) are inherently qualitative; this records the operator's
    reasoned decision rather than fabricating an automatic score.
    Flips the lazily-created one-off Offer's mode from 'concierge_only' to
    'full_payment' (making it browsable/searchable) and lifts the
    one-off max_pending_quantity cap. Idempotent: promoting an
    already-promoted offer returns the same catalog Offer. Caller must
    have already row-locked `offer`.
    """
    if offer.catalog_promoted_at is not None:
        if offer.promoted_offer_id is None:
            raise ConciergeOfferError("promoted_offer_missing")
        catalog_offer = await session.get(Offer, offer.promoted_offer_id)
        if catalog_offer is None:
            raise ConciergeOfferError("promoted_offer_missing")
        return catalog_offer
    if offer.status != "accepted" or offer.promoted_offer_id is None:
        raise ConciergeOfferError("offer_not_accepted")
    catalog_offer = await session.get(Offer, offer.promoted_offer_id, with_for_update=True)
    if catalog_offer is None:
        raise ConciergeOfferError("promoted_offer_missing")
    now = utc_now()
    catalog_offer.mode = "full_payment"
    catalog_offer.sourcing_route = "aggregated"
    catalog_offer.max_pending_quantity = None
    offer.catalog_promoted_at = now
    offer.catalog_promoted_by_operator_id = operator_id
    offer.catalog_promotion_rationale = rationale
    session.add(
        _event(offer.id, "catalog_promoted", now, operator_id=operator_id, reason=rationale)
    )
    await session.flush()
    return catalog_offer
