from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import timedelta

import httpx
import pytest
from app.api.dependencies import get_current_identity
from app.common.time import utc_now
from app.core.config import get_settings
from app.db.session import SessionFactory, close_database
from app.main import create_app
from app.modules.catalog.models import Offer, Product, Supplier
from app.modules.checkout.service import CheckoutItem, CheckoutService
from app.modules.concierge.models import ConciergeOffer
from app.modules.concierge.service import (
    ConciergeOfferError,
    OfferPresentationFacts,
    accept_offer,
    decline_offer,
    expire_stale_offers,
    mark_unavailable,
    present_offer,
    promote_to_catalog,
    request_refresh,
    start_review,
)
from app.modules.households.models import Household, HouseholdAddress, HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.orders.models import Order
from app.modules.payments.models import PaymentAttempt
from app.modules.support.models import CustomerRequest
from app.modules.trust.files import EvidenceFile
from fastapi import FastAPI
from sqlalchemy import select, update

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL is required",
)


@pytest.fixture(autouse=True)
async def dispose_engine_between_event_loops() -> AsyncIterator[None]:
    yield
    await close_database()


@pytest.fixture(scope="module", autouse=True)
def _release_concierge_only_offers_after_module() -> Iterator[None]:
    """catalog_offers.mode='concierge_only' rows this module creates would
    otherwise permanently block any later test that downgrades the
    schema past 20260720_0035 in this shared database (that migration's
    downgrade correctly re-narrows the mode CHECK constraint, and Postgres
    validates it against existing rows) -- neutralize the value once this
    module's tests finish rather than deleting rows, which would also
    need to unwind the Orders/OrderLines that reference them."""
    yield

    async def _cleanup() -> None:
        async with SessionFactory() as session:
            await session.execute(
                update(Offer)
                .where(Offer.mode == "concierge_only")
                .values(mode="full_payment")
            )
            await session.commit()
        await close_database()

    asyncio.run(_cleanup())


@pytest.fixture()
def concierge_offers_enabled() -> Iterator[None]:
    settings = get_settings()
    settings.concierge_offers_enabled = True
    try:
        yield
    finally:
        settings.concierge_offers_enabled = False


@dataclass(slots=True)
class ConciergeSeed:
    token: str
    customer_id: uuid.UUID
    operator_id: uuid.UUID
    household_id: uuid.UUID
    address_id: uuid.UUID
    request_id: uuid.UUID
    supplier_id: uuid.UUID
    evidence_file_id: uuid.UUID


async def _seed_request(*, request_type: str = "concierge_sourcing") -> ConciergeSeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98919{token[:7]}", status="active"
        )
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98918{token[:7]}", status="active"
        )
        supplier = Supplier(
            internal_name=f"concierge-supplier-{token}", country_code="DE", active=True
        )
        household = Household(name=f"hh-concierge-{token}")
        session.add_all([customer, operator, supplier, household])
        await session.flush()
        session.add(
            HouseholdMembership(household_id=household.id, identity_id=customer.id, role="owner")
        )
        address = HouseholdAddress(
            household_id=household.id,
            label="خانه",
            recipient_name="مشتری تست",
            recipient_mobile_e164="+989120000000",
            province="تهران",
            city="تهران",
            address_line="خیابان آزمایشی",
            active=True,
        )
        evidence = EvidenceFile(
            storage_key=f"evidence/{token}/supplier-invoice.pdf",
            original_filename="supplier-invoice.pdf",
            media_type="application/pdf",
            size_bytes=1024,
            checksum_sha256="a" * 64,
            uploaded_by_operator_id=operator.id,
        )
        request = CustomerRequest(
            identity_id=customer.id,
            household_id=household.id,
            request_type=request_type,
            product_query_fa=f"غذای مخصوص {token}",
            message_fa="لطفا این محصول را برایم تهیه کنید",
            contact_preference="in_app",
            status="submitted",
            idempotency_key=f"req-{token}",
        )
        session.add_all([address, evidence, request])
        await session.commit()
        return ConciergeSeed(
            token=token,
            customer_id=customer.id,
            operator_id=operator.id,
            household_id=household.id,
            address_id=address.id,
            request_id=request.id,
            supplier_id=supplier.id,
            evidence_file_id=evidence.id,
        )


def _facts(seed: ConciergeSeed, **overrides: object) -> OfferPresentationFacts:
    base: dict[str, object] = {
        "title_fa": f"محصول تایید شده {seed.token}",
        "unit_label_fa": "بسته",
        "quantity": 1,
        "authenticity_basis": "supplier_invoice_verified",
        "supplier_id": seed.supplier_id,
        "verification_evidence_file_id": seed.evidence_file_id,
        "minimum_shelf_life_months": 6,
        "estimated_delivery_days": 20,
        "pricing_mode": "reference_price_savings",
        "price_irr": 9_000_000,
        "price_explanation_fa": "قیمت بر اساس مرجع بازار و صرفه‌جویی واقعی محاسبه شده است.",
        "reference_price_irr": 10_500_000,
        "validity_hours": 24,
    }
    base.update(overrides)
    return OfferPresentationFacts(**base)  # type: ignore[arg-type]


async def _start(seed: ConciergeSeed) -> uuid.UUID:
    async with SessionFactory() as session:
        request = await session.get(CustomerRequest, seed.request_id, with_for_update=True)
        assert request is not None
        offer = await start_review(session, request=request, operator_id=seed.operator_id)
        await session.commit()
        return offer.id


async def _present(seed: ConciergeSeed, offer_id: uuid.UUID, **overrides: object) -> None:
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        await present_offer(
            session, offer=offer, operator_id=seed.operator_id, facts=_facts(seed, **overrides)
        )
        await session.commit()


async def _presented_offer(seed: ConciergeSeed, **facts_overrides: object) -> uuid.UUID:
    offer_id = await _start(seed)
    await _present(seed, offer_id, **facts_overrides)
    return offer_id


# --- service-level: start_review ---------------------------------------


async def test_start_review_creates_reviewing_and_marks_request_in_review() -> None:
    seed = await _seed_request()
    offer_id = await _start(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id)
        request = await session.get(CustomerRequest, seed.request_id)
    assert offer is not None
    assert offer.status == "reviewing"
    assert offer.reviewing_started_by_operator_id == seed.operator_id
    assert request is not None and request.status == "in_review"


async def test_start_review_is_idempotent() -> None:
    seed = await _seed_request()
    first_id = await _start(seed)
    second_id = await _start(seed)
    assert first_id == second_id
    async with SessionFactory() as session:
        count = len(
            (
                await session.scalars(
                    select(ConciergeOffer).where(ConciergeOffer.request_id == seed.request_id)
                )
            ).all()
        )
    assert count == 1


async def test_start_review_rejects_a_support_type_request() -> None:
    seed = await _seed_request(request_type="support")
    async with SessionFactory() as session:
        request = await session.get(CustomerRequest, seed.request_id, with_for_update=True)
        assert request is not None
        with pytest.raises(ConciergeOfferError, match="request_is_not_concierge_sourcing"):
            await start_review(session, request=request, operator_id=seed.operator_id)


# --- service-level: present_offer ---------------------------------------


async def test_present_offer_with_reference_price_savings() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id)
    assert offer is not None
    assert offer.status == "offer_presented"
    assert offer.pricing_mode == "reference_price_savings"
    assert offer.price_irr == 9_000_000
    assert offer.reference_price_irr == 10_500_000
    assert offer.expires_at is not None
    assert offer.expires_at - offer.presented_at == timedelta(hours=24)


async def test_present_offer_with_landed_cost_plus_margin() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(
        seed,
        pricing_mode="landed_cost_plus_margin",
        reference_price_irr=None,
        supplier_cost_irr=5_000_000,
        international_transport_irr=1_000_000,
        customs_clearance_irr=500_000,
        platform_margin_irr=1_500_000,
    )
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id)
    assert offer is not None
    assert offer.pricing_mode == "landed_cost_plus_margin"
    assert offer.supplier_cost_irr == 5_000_000
    assert offer.platform_margin_irr == 1_500_000


async def test_present_offer_requires_reference_price_for_that_mode() -> None:
    seed = await _seed_request()
    offer_id = await _start(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        with pytest.raises(ConciergeOfferError, match="reference_price_required"):
            await present_offer(
                session,
                offer=offer,
                operator_id=seed.operator_id,
                facts=_facts(seed, reference_price_irr=None),
            )


async def test_present_offer_requires_landed_cost_components_for_that_mode() -> None:
    seed = await _seed_request()
    offer_id = await _start(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        with pytest.raises(ConciergeOfferError, match="landed_cost_components_required"):
            await present_offer(
                session,
                offer=offer,
                operator_id=seed.operator_id,
                facts=_facts(
                    seed,
                    pricing_mode="landed_cost_plus_margin",
                    reference_price_irr=None,
                ),
            )


async def test_present_offer_rejects_out_of_range_validity_hours() -> None:
    seed = await _seed_request()
    offer_id = await _start(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        with pytest.raises(ConciergeOfferError, match="validity_hours_out_of_range"):
            await present_offer(
                session,
                offer=offer,
                operator_id=seed.operator_id,
                facts=_facts(seed, validity_hours=72),
            )


async def test_present_offer_is_idempotent_and_immutable_once_presented() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        result = await present_offer(
            session,
            offer=offer,
            operator_id=seed.operator_id,
            facts=_facts(seed, price_irr=1),
        )
    assert result.price_irr == 9_000_000


# --- service-level: mark_unavailable -------------------------------------


async def test_mark_unavailable_resolves_the_request() -> None:
    seed = await _seed_request()
    offer_id = await _start(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        await mark_unavailable(
            session, offer=offer, operator_id=seed.operator_id, reason="عدم دسترسی به تامین‌کننده"
        )
        await session.commit()
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id)
        request = await session.get(CustomerRequest, seed.request_id)
    assert offer is not None and offer.status == "unavailable"
    assert request is not None and request.status == "resolved"


async def test_mark_unavailable_is_idempotent() -> None:
    seed = await _seed_request()
    offer_id = await _start(seed)

    async def _mark_once() -> ConciergeOffer:
        async with SessionFactory() as session:
            offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
            assert offer is not None
            result = await mark_unavailable(
                session, offer=offer, operator_id=seed.operator_id, reason="no supplier"
            )
            await session.commit()
            return result

    first = await _mark_once()
    second = await _mark_once()
    assert first.unavailable_reason == second.unavailable_reason == "no supplier"


async def test_mark_unavailable_rejects_an_already_presented_offer() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        with pytest.raises(ConciergeOfferError, match="offer_not_open_for_unavailable"):
            await mark_unavailable(
                session, offer=offer, operator_id=seed.operator_id, reason="too late"
            )


# --- service-level: accept_offer ------------------------------------------


async def test_accept_offer_creates_a_hidden_one_off_catalog_offer_and_order() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        offer, order = await accept_offer(
            session,
            offer=offer,
            customer_identity_id=seed.customer_id,
            address_id=seed.address_id,
        )
    assert order.status == "awaiting_payment"
    assert order.merchandise_total_irr == 9_000_000
    assert offer.status == "accepted"
    assert offer.promoted_offer_id is not None
    assert offer.resulting_order_id == order.id
    async with SessionFactory() as session:
        catalog_offer = await session.get(Offer, offer.promoted_offer_id)
        request = await session.get(CustomerRequest, seed.request_id)
    assert catalog_offer is not None
    assert catalog_offer.mode == "concierge_only"
    assert catalog_offer.sourcing_route == "individual"
    assert catalog_offer.max_pending_quantity == 1
    assert request is not None and request.status == "resolved"


async def test_crash_between_order_creation_and_offer_acceptance_leaves_no_orphan() -> None:
    """Fault injection (Workstream 2): replicates accept_offer's own
    sequence (create the one-off product/offer, then construct the order)
    up to but not including its atomic commit, then simulates a crash by
    rolling back instead of continuing to mutate offer.status. Nothing
    from either step may survive, and a subsequent real accept_offer call
    must still succeed cleanly."""
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    idempotency_key = f"concierge:{offer_id}"

    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        assert offer.supplier_id is not None and offer.title_fa is not None
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
        await CheckoutService().create_order_uncommitted(
            session,
            customer_identity_id=seed.customer_id,
            household_id=offer.household_id,
            address_id=seed.address_id,
            items=[CheckoutItem(catalog_offer.id, offer.quantity)],
            idempotency_key=idempotency_key,
            allowed_modes=frozenset({"concierge_only"}),
        )
        # Simulated crash: never reach offer.status = "accepted" or commit.
        await session.rollback()

    async with SessionFactory() as session:
        orphan_order = await session.scalar(
            select(Order).where(
                Order.customer_identity_id == seed.customer_id,
                Order.checkout_idempotency_key == idempotency_key,
            )
        )
        assert orphan_order is None
        orphan_offer = await session.scalar(
            select(Offer).where(Offer.sku == f"CONCIERGE-{offer_id}")
        )
        assert orphan_offer is None
        untouched = await session.get(ConciergeOffer, offer_id)
        assert untouched is not None and untouched.status == "offer_presented"

    # A real, subsequent accept_offer call must succeed cleanly -- no
    # leftover state from the simulated crash blocks it.
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        offer, order = await accept_offer(
            session,
            offer=offer,
            customer_identity_id=seed.customer_id,
            address_id=seed.address_id,
        )
    assert offer.status == "accepted"
    assert order.checkout_idempotency_key == idempotency_key


async def test_accept_offer_does_not_auto_charge() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        _, order = await accept_offer(
            session,
            offer=offer,
            customer_identity_id=seed.customer_id,
            address_id=seed.address_id,
        )
        order_id = order.id
    async with SessionFactory() as session:
        payment_count = len(
            (
                await session.scalars(
                    select(PaymentAttempt).where(PaymentAttempt.order_id == order_id)
                )
            ).all()
        )
    assert payment_count == 0


async def test_accept_offer_is_idempotent_and_returns_the_same_order() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)

    async def _accept_once() -> uuid.UUID:
        async with SessionFactory() as session:
            offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
            assert offer is not None
            _, order = await accept_offer(
                session,
                offer=offer,
                customer_identity_id=seed.customer_id,
                address_id=seed.address_id,
            )
            return order.id

    first_order_id = await _accept_once()
    second_order_id = await _accept_once()
    assert first_order_id == second_order_id
    async with SessionFactory() as session:
        order_count = len(
            (
                await session.scalars(
                    select(Order).where(Order.household_id == seed.household_id)
                )
            ).all()
        )
    assert order_count == 1


async def test_accept_offer_after_deadline_expires_instead() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        offer.expires_at = utc_now() - timedelta(hours=1)
        await session.commit()
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        with pytest.raises(ConciergeOfferError, match="offer_validity_expired"):
            await accept_offer(
                session,
                offer=offer,
                customer_identity_id=seed.customer_id,
                address_id=seed.address_id,
            )
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id)
    assert offer is not None and offer.status == "expired"


# --- service-level: decline_offer -----------------------------------------


async def test_decline_offer_resolves_the_request() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        await decline_offer(
            session,
            offer=offer,
            customer_identity_id=seed.customer_id,
            reason="قیمت مناسب نیست",
        )
        await session.commit()
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id)
        request = await session.get(CustomerRequest, seed.request_id)
    assert offer is not None and offer.status == "declined"
    assert request is not None and request.status == "resolved"


async def test_decline_offer_is_idempotent() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)

    async def _decline_once() -> ConciergeOffer:
        async with SessionFactory() as session:
            offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
            assert offer is not None
            result = await decline_offer(
                session, offer=offer, customer_identity_id=seed.customer_id, reason=None
            )
            await session.commit()
            return result

    first = await _decline_once()
    second = await _decline_once()
    assert first.responded_at == second.responded_at


async def test_decline_offer_after_deadline_expires_instead() -> None:
    """Mirrors test_accept_offer_after_deadline_expires_instead: discovering
    the deadline has passed during a decline attempt must persist the
    expiry transition just as reliably as discovering it during an accept
    attempt, even though decline_offer itself raises rather than returning
    normally (gap-closure fix -- this used to be silently rolled back)."""
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        offer.expires_at = utc_now() - timedelta(hours=1)
        await session.commit()
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        with pytest.raises(ConciergeOfferError, match="offer_validity_expired"):
            await decline_offer(
                session,
                offer=offer,
                customer_identity_id=seed.customer_id,
                reason="دیگر لازم نیست",
            )
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id)
    assert offer is not None and offer.status == "expired"


# --- service-level: request_refresh ----------------------------------------


async def test_request_refresh_creates_a_new_cycle_without_touching_the_old_row() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        offer.expires_at = utc_now() - timedelta(hours=1)
        offer.status = "expired"
        await session.commit()

    async with SessionFactory() as session:
        expired = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert expired is not None
        refreshed = await request_refresh(
            session, expired_offer=expired, customer_identity_id=seed.customer_id
        )
        await session.commit()
        refreshed_id = refreshed.id

    async with SessionFactory() as session:
        expired = await session.get(ConciergeOffer, offer_id)
        refreshed = await session.get(ConciergeOffer, refreshed_id)
        request = await session.get(CustomerRequest, seed.request_id)
    assert expired is not None and expired.status == "expired"
    assert expired.responded_at is None
    assert refreshed is not None
    assert refreshed.status == "refresh_requested"
    assert refreshed.refreshed_from_offer_id == offer_id
    assert request is not None and request.status == "submitted"


async def test_request_refresh_is_idempotent_while_a_cycle_is_active() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        offer.expires_at = utc_now() - timedelta(hours=1)
        offer.status = "expired"
        await session.commit()

    async def _refresh_once() -> uuid.UUID:
        async with SessionFactory() as session:
            expired = await session.get(ConciergeOffer, offer_id, with_for_update=True)
            assert expired is not None
            refreshed = await request_refresh(
                session, expired_offer=expired, customer_identity_id=seed.customer_id
            )
            await session.commit()
            return refreshed.id

    first_id = await _refresh_once()
    second_id = await _refresh_once()
    assert first_id == second_id
    async with SessionFactory() as session:
        count = len(
            (
                await session.scalars(
                    select(ConciergeOffer).where(
                        ConciergeOffer.request_id == seed.request_id,
                        ConciergeOffer.status == "refresh_requested",
                    )
                )
            ).all()
        )
    assert count == 1


async def test_request_refresh_rejects_a_non_expired_offer() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        with pytest.raises(ConciergeOfferError, match="offer_not_expired"):
            await request_refresh(
                session, expired_offer=offer, customer_identity_id=seed.customer_id
            )


# --- expiry sweep ----------------------------------------------------------


async def test_expire_stale_offers_expires_past_deadline_only() -> None:
    fresh_seed = await _seed_request()
    stale_seed = await _seed_request()
    fresh_id = await _presented_offer(fresh_seed)
    stale_id = await _presented_offer(stale_seed)

    async with SessionFactory() as session:
        stale = await session.get(ConciergeOffer, stale_id, with_for_update=True)
        assert stale is not None
        stale.expires_at = utc_now() - timedelta(hours=1)
        await session.commit()

    expired_count = await expire_stale_offers(SessionFactory)
    assert expired_count >= 1

    async with SessionFactory() as session:
        fresh = await session.get(ConciergeOffer, fresh_id)
        stale = await session.get(ConciergeOffer, stale_id)
        stale_request = await session.get(CustomerRequest, stale_seed.request_id)
    assert fresh is not None and fresh.status == "offer_presented"
    assert stale is not None and stale.status == "expired"
    assert stale_request is not None and stale_request.status == "resolved"


# --- catalog promotion -----------------------------------------------------


async def test_promote_to_catalog_flips_mode_and_lifts_the_quantity_cap() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        await accept_offer(
            session,
            offer=offer,
            customer_identity_id=seed.customer_id,
            address_id=seed.address_id,
        )

    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        catalog_offer = await promote_to_catalog(
            session,
            offer=offer,
            operator_id=seed.operator_id,
            rationale="تقاضای تکراری و تامین پایدار در سه ماه گذشته",
        )
        await session.commit()
    assert catalog_offer.mode == "full_payment"
    assert catalog_offer.sourcing_route == "aggregated"
    assert catalog_offer.max_pending_quantity is None
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id)
    assert offer is not None and offer.catalog_promoted_at is not None


async def test_promote_to_catalog_rejects_a_non_accepted_offer() -> None:
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        with pytest.raises(ConciergeOfferError, match="offer_not_accepted"):
            await promote_to_catalog(
                session, offer=offer, operator_id=seed.operator_id, rationale="too early"
            )


# --- concurrency -------------------------------------------------------


async def _race_accept(seed: ConciergeSeed, offer_id: uuid.UUID, *, delay: float = 0.0) -> str:
    if delay:
        await asyncio.sleep(delay)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        try:
            await accept_offer(
                session,
                offer=offer,
                customer_identity_id=seed.customer_id,
                address_id=seed.address_id,
            )
        except ConciergeOfferError:
            await session.rollback()
            return "rejected"
        return "accepted"


async def _race_decline(seed: ConciergeSeed, offer_id: uuid.UUID, *, delay: float = 0.0) -> str:
    if delay:
        await asyncio.sleep(delay)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        try:
            await decline_offer(
                session,
                offer=offer,
                customer_identity_id=seed.customer_id,
                reason="race test",
            )
        except ConciergeOfferError:
            await session.rollback()
            return "rejected"
        await session.commit()
        return "declined"


async def test_concurrent_accept_and_decline_never_both_succeed() -> None:
    accept_wins = 0
    decline_wins = 0
    for trial in range(8):
        seed = await _seed_request()
        offer_id = await _presented_offer(seed)

        give_accept_a_head_start = trial % 2 == 0
        accept_result, decline_result = await asyncio.gather(
            _race_accept(seed, offer_id, delay=0.0 if give_accept_a_head_start else 0.05),
            _race_decline(seed, offer_id, delay=0.05 if give_accept_a_head_start else 0.0),
        )
        outcomes = {accept_result, decline_result}
        assert outcomes in ({"accepted", "rejected"}, {"declined", "rejected"})
        if accept_result == "accepted":
            accept_wins += 1
        else:
            decline_wins += 1

        async with SessionFactory() as session:
            order_count = len(
                (
                    await session.scalars(
                        select(Order).where(Order.household_id == seed.household_id)
                    )
                ).all()
            )
        async with SessionFactory() as session:
            offer = await session.get(ConciergeOffer, offer_id)
            offer_status = offer.status if offer else None
        if offer_status == "accepted":
            assert order_count == 1
        else:
            assert offer_status == "declined"
            assert order_count == 0

    assert accept_wins > 0
    assert decline_wins > 0


# --- HTTP layer: gating -------------------------------------------------------


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def test_http_concierge_offer_endpoints_are_disabled_by_default(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_request()
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer

    assert get_settings().concierge_offers_enabled is False

    listed = await client.get(f"/api/v1/customer-requests/{seed.request_id}/concierge-offers")
    assert listed.status_code == 409
    assert listed.json()["error"]["code"] == "concierge_offers_disabled"


# --- HTTP layer: full lifecycle ------------------------------------------------


async def test_http_full_concierge_offer_lifecycle(
    concierge_offers_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_request()
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, seed.customer_id)
        operator = await session.get(AuthIdentity, seed.operator_id)

    app.dependency_overrides[get_current_identity] = lambda: operator
    started = await client.post(
        f"/api/v1/operator/customer-requests/{seed.request_id}/concierge-offers/start-review"
    )
    assert started.status_code == 200
    body = started.json()
    assert body["status"] == "reviewing"
    assert "supplier_id" in body
    offer_id = body["id"]

    presented = await client.post(
        f"/api/v1/operator/concierge-offers/{offer_id}/present",
        json={
            "title_fa": "محصول تایید‌شده کنسیرژ",
            "unit_label_fa": "بسته",
            "quantity": 1,
            "authenticity_basis": "supplier_invoice_verified",
            "supplier_id": str(seed.supplier_id),
            "verification_evidence_file_id": str(seed.evidence_file_id),
            "minimum_shelf_life_months": 6,
            "estimated_delivery_days": 20,
            "pricing_mode": "reference_price_savings",
            "price_irr": 9_000_000,
            "reference_price_irr": 10_500_000,
            "price_explanation_fa": "صرفه‌جویی واقعی نسبت به قیمت مرجع بازار.",
        },
    )
    assert presented.status_code == 200
    assert presented.json()["status"] == "offer_presented"
    # Operator response carries internal fields; the same offer must never
    # leak them to the customer-facing endpoint (checked below).
    assert "supplier_cost_irr" in presented.json()

    app.dependency_overrides[get_current_identity] = lambda: customer
    listed = await client.get(f"/api/v1/customer-requests/{seed.request_id}/concierge-offers")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    customer_body = listed.json()[0]
    assert customer_body["id"] == offer_id
    assert customer_body["price_irr"] == 9_000_000
    assert customer_body["supplier_country_code"] == "DE"
    assert "supplier_id" not in customer_body
    assert "supplier_cost_irr" not in customer_body
    assert "platform_margin_irr" not in customer_body

    accepted = await client.post(
        f"/api/v1/concierge-offers/{offer_id}/accept",
        json={"address_id": str(seed.address_id)},
    )
    assert accepted.status_code == 200
    accepted_body = accepted.json()
    assert accepted_body["status"] == "accepted"
    assert accepted_body["resulting_order_id"] is not None
    assert accepted_body["auto_charged"] is False


async def test_http_decline_concierge_offer(
    concierge_offers_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer

    declined = await client.post(
        f"/api/v1/concierge-offers/{offer_id}/decline",
        json={"reason": "دیگر لازم نیست"},
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"


async def test_http_refresh_concierge_offer(
    concierge_offers_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        offer.expires_at = utc_now() - timedelta(hours=1)
        offer.status = "expired"
        await session.commit()
        customer = await session.get(AuthIdentity, seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer

    refreshed = await client.post(f"/api/v1/concierge-offers/{offer_id}/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "refresh_requested"
    assert refreshed.json()["refreshed_from_offer_id"] == str(offer_id)


async def test_http_concierge_offer_is_non_enumerating_for_a_foreign_customer(
    concierge_offers_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        outsider = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98917{seed.token[:7]}", status="active"
        )
        session.add(outsider)
        await session.commit()
        outsider_id = outsider.id
    async with SessionFactory() as session:
        outsider_obj = await session.get(AuthIdentity, outsider_id)
    app.dependency_overrides[get_current_identity] = lambda: outsider_obj

    nonexistent = await client.get(f"/api/v1/concierge-offers/{uuid.uuid4()}")
    foreign = await client.get(f"/api/v1/concierge-offers/{offer_id}")
    assert nonexistent.status_code == foreign.status_code == 404
    assert nonexistent.json()["error"]["code"] == foreign.json()["error"]["code"]


async def test_concierge_offer_mutations_are_non_enumerating_for_a_foreign_customer(
    concierge_offers_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    accept_seed = await _seed_request()
    accept_offer_id = await _presented_offer(accept_seed)
    decline_seed = await _seed_request()
    decline_offer_id = await _presented_offer(decline_seed)
    refresh_seed = await _seed_request()
    refresh_offer_id = await _presented_offer(refresh_seed)
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, refresh_offer_id, with_for_update=True)
        assert offer is not None
        offer.expires_at = utc_now() - timedelta(hours=1)
        offer.status = "expired"
        await session.commit()
        outsider = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98924{accept_seed.token[:7]}", status="active"
        )
        session.add(outsider)
        await session.commit()
        outsider_id = outsider.id
    async with SessionFactory() as session:
        outsider_obj = await session.get(AuthIdentity, outsider_id)
    app.dependency_overrides[get_current_identity] = lambda: outsider_obj

    accepted = await client.post(
        f"/api/v1/concierge-offers/{accept_offer_id}/accept",
        json={"address_id": str(accept_seed.address_id)},
    )
    assert accepted.status_code == 404

    declined = await client.post(
        f"/api/v1/concierge-offers/{decline_offer_id}/decline",
        json={"reason": "این پیشنهاد من نیست"},
    )
    assert declined.status_code == 404

    refreshed = await client.post(f"/api/v1/concierge-offers/{refresh_offer_id}/refresh")
    assert refreshed.status_code == 404

    async with SessionFactory() as session:
        untouched_accept = await session.get(ConciergeOffer, accept_offer_id)
        untouched_decline = await session.get(ConciergeOffer, decline_offer_id)
        assert untouched_accept is not None and untouched_accept.status == "offer_presented"
        assert untouched_decline is not None and untouched_decline.status == "offer_presented"


async def test_http_operator_queue_filters_by_status(
    concierge_offers_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    reviewing_seed = await _seed_request()
    presented_seed = await _seed_request()
    await _start(reviewing_seed)
    await _presented_offer(presented_seed)
    async with SessionFactory() as session:
        operator = await session.get(AuthIdentity, reviewing_seed.operator_id)
    app.dependency_overrides[get_current_identity] = lambda: operator

    response = await client.get(
        "/api/v1/operator/concierge-offers", params={"status": "offer_presented", "limit": 100}
    )
    assert response.status_code == 200
    items = response.json()["items"]
    statuses = {item["status"] for item in items}
    assert statuses <= {"offer_presented"}
    assert any(item["household_id"] == str(presented_seed.household_id) for item in items)


async def test_http_operator_concierge_routes_require_operator_role(
    concierge_offers_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_request()
    offer_id = await _presented_offer(seed)
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer

    listed = await client.get("/api/v1/operator/concierge-offers")
    assert listed.status_code == 403
    detail = await client.get(f"/api/v1/operator/concierge-offers/{offer_id}")
    assert detail.status_code == 403
    started = await client.post(
        f"/api/v1/operator/customer-requests/{seed.request_id}/concierge-offers/start-review"
    )
    assert started.status_code == 403
    presented = await client.post(
        f"/api/v1/operator/concierge-offers/{offer_id}/present",
        json={
            "title_fa": "x",
            "unit_label_fa": "x",
            "authenticity_basis": "supplier_invoice_verified",
            "supplier_id": str(seed.supplier_id),
            "verification_evidence_file_id": str(seed.evidence_file_id),
            "minimum_shelf_life_months": 6,
            "estimated_delivery_days": 20,
            "pricing_mode": "reference_price_savings",
            "price_irr": 1_000_000,
            "reference_price_irr": 1_200_000,
            "price_explanation_fa": "x",
        },
    )
    assert presented.status_code == 403
    unavailable = await client.post(
        f"/api/v1/operator/concierge-offers/{offer_id}/unavailable",
        json={"reason": "a customer should never reach this"},
    )
    assert unavailable.status_code == 403
    promoted = await client.post(
        f"/api/v1/operator/concierge-offers/{offer_id}/promote",
        json={"rationale": "a customer should never reach this"},
    )
    assert promoted.status_code == 403


# --- catalog hiding ----------------------------------------------------------


async def test_accepted_concierge_offer_is_hidden_from_browse_search_and_direct_id(
    concierge_offers_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    """Hardened by the gap-closure security pass: the public catalog detail
    route is fully unauthenticated, so "reachable by id" was equivalent to
    "disclosed to anyone who has or guesses the id" -- direct-id
    enumeration must not disclose a concierge_only offer (bound to one
    specific customer's verified, priced sourcing arrangement) to anyone
    else. The owning customer views it via the ownership-checked
    GET /concierge-offers/{offer_id} route and their order detail's own
    price/title snapshot instead -- neither depends on the public catalog
    route staying open for this mode."""
    app, client = app_and_client
    seed = await _seed_request()
    offer_id = await _presented_offer(
        seed, title_fa=f"محصول قابل جستجو {seed.token}"
    )
    async with SessionFactory() as session:
        offer = await session.get(ConciergeOffer, offer_id, with_for_update=True)
        assert offer is not None
        offer, _ = await accept_offer(
            session,
            offer=offer,
            customer_identity_id=seed.customer_id,
            address_id=seed.address_id,
        )
        promoted_offer_id = offer.promoted_offer_id
        await session.commit()
    assert promoted_offer_id is not None

    browse = await client.get("/api/v1/catalog/offers")
    assert browse.status_code == 200
    assert str(promoted_offer_id) not in {item["id"] for item in browse.json()}

    search = await client.get(
        "/api/v1/catalog/offers/search",
        params={"q": f"CONCIERGE-{offer_id}", "limit": 50},
    )
    assert search.status_code == 200
    assert search.json()["page"]["total"] == 0

    direct = await client.get(f"/api/v1/catalog/offers/{promoted_offer_id}")
    nonexistent = await client.get(f"/api/v1/catalog/offers/{uuid.uuid4()}")
    assert direct.status_code == nonexistent.status_code == 404
