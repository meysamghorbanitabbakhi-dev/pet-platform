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
from app.modules.households.models import Household, HouseholdAddress, HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.orders.models import Order, OrderLine
from app.modules.reservations.models import Reservation
from app.modules.reservations.service import (
    ReservationError,
    approve_and_convert_reservation,
    decline_reservation,
    expire_stale_reservations,
    operator_decline_reservation,
    reconfirm_and_propose_reservation,
    request_reservation,
)
from fastapi import FastAPI
from sqlalchemy import select

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL is required",
)


@pytest.fixture(autouse=True)
async def dispose_engine_between_event_loops() -> AsyncIterator[None]:
    yield
    await close_database()


@pytest.fixture()
def reserve_now_enabled() -> Iterator[None]:
    settings = get_settings()
    settings.reserve_now_enabled = True
    try:
        yield
    finally:
        settings.reserve_now_enabled = False


@dataclass(slots=True)
class ReservationSeed:
    token: str
    operator_id: uuid.UUID
    customer_id: uuid.UUID
    household_id: uuid.UUID
    address_id: uuid.UUID
    offer_id: uuid.UUID
    offer_price_irr: int


async def _seed_reservable_offer(
    *, offer_price_irr: int = 8_000_000, mode: str = "reserve"
) -> ReservationSeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98918{token[:7]}", status="active"
        )
        customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98919{token[:7]}", status="active"
        )
        supplier = Supplier(
            internal_name=f"reserve-supplier-{token}", country_code="FR", active=True
        )
        product = Product(name_fa=f"محصول رزرو {token}", status="active")
        household = Household(name=f"hh-reserve-{token}")
        session.add_all([operator, customer, supplier, product, household])
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
        offer = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"RESERVE-{token}",
            title_fa=f"پیشنهاد رزرو {token}",
            unit_label_fa="عدد",
            price_irr=offer_price_irr,
            status="active",
            stock_posture="sourced_after_payment",
            sourcing_capacity_status="open",
            sourcing_route="individual",
            minimum_shelf_life_months=6,
            mode=mode,
        )
        session.add_all([address, offer])
        await session.commit()
        return ReservationSeed(
            token=token,
            operator_id=operator.id,
            customer_id=customer.id,
            household_id=household.id,
            address_id=address.id,
            offer_id=offer.id,
            offer_price_irr=offer_price_irr,
        )


async def _request(seed: ReservationSeed, *, quantity: int = 1) -> uuid.UUID:
    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        reservation = await request_reservation(
            session,
            offer=offer,
            customer_identity_id=seed.customer_id,
            household_id=seed.household_id,
            quantity=quantity,
            idempotency_key=f"req-{uuid.uuid4().hex}",
        )
        await session.commit()
        return reservation.id


async def _propose(
    seed: ReservationSeed,
    reservation_id: uuid.UUID,
    *,
    reconfirmed_price_irr: int,
    reconfirmed_available: bool = True,
    response_window_hours: int = 48,
) -> None:
    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id, with_for_update=True)
        assert reservation is not None
        await reconfirm_and_propose_reservation(
            session,
            reservation=reservation,
            operator_id=seed.operator_id,
            reconfirmed_price_irr=reconfirmed_price_irr,
            reconfirmed_available=reconfirmed_available,
            reason="قیمت و موجودی از تامین‌کننده تایید شد",
            response_window_hours=response_window_hours,
        )
        await session.commit()


# --- service-level: request --------------------------------------------


async def test_request_reservation_is_zero_charge_and_requested() -> None:
    seed = await _seed_reservable_offer()
    reservation_id = await _request(seed, quantity=2)
    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id)
    assert reservation is not None
    assert reservation.status == "requested"
    assert reservation.quantity == 2
    assert reservation.requested_price_irr == seed.offer_price_irr
    # No order, no payment attempt of any kind exists at this point.
    async with SessionFactory() as session:
        order_count = len(
            (
                await session.scalars(select(Order).where(Order.household_id == seed.household_id))
            ).all()
        )
    assert order_count == 0


async def test_request_reservation_rejects_a_full_payment_offer() -> None:
    seed = await _seed_reservable_offer(mode="full_payment")
    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        with pytest.raises(ReservationError):
            await request_reservation(
                session,
                offer=offer,
                customer_identity_id=seed.customer_id,
                household_id=seed.household_id,
                quantity=1,
                idempotency_key="x",
            )


async def test_request_reservation_is_idempotent_on_replay() -> None:
    seed = await _seed_reservable_offer()
    key = f"req-{uuid.uuid4().hex}"
    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        first = await request_reservation(
            session,
            offer=offer,
            customer_identity_id=seed.customer_id,
            household_id=seed.household_id,
            quantity=1,
            idempotency_key=key,
        )
        await session.commit()
    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        second = await request_reservation(
            session,
            offer=offer,
            customer_identity_id=seed.customer_id,
            household_id=seed.household_id,
            quantity=1,
            idempotency_key=key,
        )
        await session.commit()
    assert first.id == second.id


# --- service-level: reconfirm/propose, decline --------------------------


async def test_reconfirm_and_propose_sets_terms_and_deadline() -> None:
    seed = await _seed_reservable_offer(offer_price_irr=8_000_000)
    reservation_id = await _request(seed)
    await _propose(seed, reservation_id, reconfirmed_price_irr=8_500_000)
    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id)
    assert reservation is not None
    assert reservation.status == "proposed"
    assert reservation.reconfirmed_price_irr == 8_500_000
    assert reservation.customer_respond_by is not None


async def test_reconfirm_and_propose_is_idempotent_on_replay() -> None:
    seed = await _seed_reservable_offer()
    reservation_id = await _request(seed)
    await _propose(seed, reservation_id, reconfirmed_price_irr=8_500_000)
    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id)
        first_respond_by = reservation.customer_respond_by if reservation else None
    await _propose(seed, reservation_id, reconfirmed_price_irr=9_999_999)
    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id)
    assert reservation is not None
    # Replay is a no-op: the second, different price never overwrote the first.
    assert reservation.reconfirmed_price_irr == 8_500_000
    assert reservation.customer_respond_by == first_respond_by


async def test_operator_decline_before_any_proposal() -> None:
    seed = await _seed_reservable_offer()
    reservation_id = await _request(seed)
    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id, with_for_update=True)
        assert reservation is not None
        result = await operator_decline_reservation(
            session,
            reservation=reservation,
            operator_id=seed.operator_id,
            reason="تامین‌کننده دیگر این کالا را ندارد",
        )
        await session.commit()
    assert result.status == "operator_declined"


async def test_customer_decline_after_proposal() -> None:
    seed = await _seed_reservable_offer()
    reservation_id = await _request(seed)
    await _propose(seed, reservation_id, reconfirmed_price_irr=8_500_000)
    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id, with_for_update=True)
        assert reservation is not None
        result = await decline_reservation(
            session,
            reservation=reservation,
            customer_identity_id=seed.customer_id,
            reason="قیمت جدید مناسب نیست",
        )
        await session.commit()
    assert result.status == "customer_declined"


async def test_customer_decline_is_idempotent() -> None:
    seed = await _seed_reservable_offer()
    reservation_id = await _request(seed)
    await _propose(seed, reservation_id, reconfirmed_price_irr=8_500_000)

    async def _decline_once() -> Reservation:
        async with SessionFactory() as session:
            reservation = await session.get(Reservation, reservation_id, with_for_update=True)
            assert reservation is not None
            result = await decline_reservation(
                session, reservation=reservation, customer_identity_id=seed.customer_id, reason=None
            )
            await session.commit()
            return result

    first = await _decline_once()
    second = await _decline_once()
    assert first.responded_at == second.responded_at


# --- service-level: approve/convert --------------------------------------


async def test_approve_converts_at_the_reconfirmed_price_not_the_live_offer_price() -> None:
    seed = await _seed_reservable_offer(offer_price_irr=8_000_000)
    reservation_id = await _request(seed, quantity=2)
    await _propose(seed, reservation_id, reconfirmed_price_irr=8_500_000)

    async with SessionFactory() as session:
        # The live offer price changes again after reconfirmation -- the
        # order must still charge the reconfirmed price, not this.
        offer = await session.get(Offer, seed.offer_id, with_for_update=True)
        assert offer is not None
        offer.price_irr = 12_000_000
        await session.commit()

    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id, with_for_update=True)
        offer = await session.get(Offer, seed.offer_id)
        supplier = await session.get(Supplier, offer.supplier_id) if offer else None
        address = await session.get(HouseholdAddress, seed.address_id)
        assert reservation is not None and offer is not None and supplier is not None
        assert address is not None
        _, order = await approve_and_convert_reservation(
            session,
            reservation=reservation,
            offer=offer,
            supplier=supplier,
            address=address,
            customer_identity_id=seed.customer_id,
        )
        await session.commit()

    assert order.status == "awaiting_payment"
    assert order.merchandise_total_irr == 8_500_000 * 2
    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id)
    assert reservation is not None
    assert reservation.status == "converted"
    assert reservation.order_id == order.id


async def test_approve_is_idempotent_and_returns_the_same_order() -> None:
    seed = await _seed_reservable_offer()
    reservation_id = await _request(seed)
    await _propose(seed, reservation_id, reconfirmed_price_irr=8_500_000)

    async def _approve_once() -> uuid.UUID:
        async with SessionFactory() as session:
            reservation = await session.get(Reservation, reservation_id, with_for_update=True)
            offer = await session.get(Offer, seed.offer_id)
            supplier = await session.get(Supplier, offer.supplier_id) if offer else None
            address = await session.get(HouseholdAddress, seed.address_id)
            assert reservation is not None and offer is not None and supplier is not None
            assert address is not None
            _, order = await approve_and_convert_reservation(
                session,
                reservation=reservation,
                offer=offer,
                supplier=supplier,
                address=address,
                customer_identity_id=seed.customer_id,
            )
            await session.commit()
            return order.id

    first_order_id = await _approve_once()
    second_order_id = await _approve_once()
    assert first_order_id == second_order_id
    async with SessionFactory() as session:
        order_count = len(
            (
                await session.scalars(select(Order).where(Order.household_id == seed.household_id))
            ).all()
        )
    assert order_count == 1


async def test_approve_rejects_a_reconfirmation_that_says_not_available() -> None:
    """Workstream 3 gap closure: an operator can propose reconfirmed terms
    with reconfirmed_available=False (an honest "we checked and it isn't
    actually available" update) -- approval must never convert that into
    a real order."""
    seed = await _seed_reservable_offer()
    reservation_id = await _request(seed)
    await _propose(
        seed, reservation_id, reconfirmed_price_irr=8_500_000, reconfirmed_available=False
    )

    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id, with_for_update=True)
        offer = await session.get(Offer, seed.offer_id)
        supplier = await session.get(Supplier, offer.supplier_id) if offer else None
        address = await session.get(HouseholdAddress, seed.address_id)
        assert reservation is not None and offer is not None and supplier is not None
        assert address is not None
        with pytest.raises(ReservationError, match="reservation_not_available"):
            await approve_and_convert_reservation(
                session,
                reservation=reservation,
                offer=offer,
                supplier=supplier,
                address=address,
                customer_identity_id=seed.customer_id,
            )
        await session.rollback()

    async with SessionFactory() as session:
        order_count = len(
            (
                await session.scalars(select(Order).where(Order.household_id == seed.household_id))
            ).all()
        )
    assert order_count == 0


async def test_approve_rejects_an_offer_that_became_unavailable_after_proposal() -> None:
    """Workstream 3 gap closure: the offer itself can be paused/retired by
    an operator in the window between proposal and the customer's
    approval click -- approval must re-check, not trust the reconfirmed
    snapshot alone for offer-level state that can change independently."""
    seed = await _seed_reservable_offer()
    reservation_id = await _request(seed)
    await _propose(seed, reservation_id, reconfirmed_price_irr=8_500_000)

    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id, with_for_update=True)
        assert offer is not None
        offer.sourcing_capacity_status = "paused"
        await session.commit()

    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id, with_for_update=True)
        offer = await session.get(Offer, seed.offer_id)
        supplier = await session.get(Supplier, offer.supplier_id) if offer else None
        address = await session.get(HouseholdAddress, seed.address_id)
        assert reservation is not None and offer is not None and supplier is not None
        assert address is not None
        with pytest.raises(ReservationError, match="offer_unavailable"):
            await approve_and_convert_reservation(
                session,
                reservation=reservation,
                offer=offer,
                supplier=supplier,
                address=address,
                customer_identity_id=seed.customer_id,
            )
        await session.rollback()


async def test_approve_rejects_when_offer_capacity_is_exhausted_by_other_orders() -> None:
    """Workstream 3 gap closure: capacity can be consumed by other orders
    (an ordinary full_payment sibling offer scenario is not applicable
    here, but a second reservation converting first against the same
    capped offer is) between proposal and approval."""
    seed = await _seed_reservable_offer()
    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id, with_for_update=True)
        assert offer is not None
        offer.max_pending_quantity = 1
        await session.commit()

    reservation_id = await _request(seed, quantity=1)
    await _propose(seed, reservation_id, reconfirmed_price_irr=8_500_000)

    # A sibling order consumes the offer's only unit of capacity first.
    async with SessionFactory() as session:
        other_customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98920{seed.token[:7]}", status="active"
        )
        session.add(other_customer)
        await session.flush()
        session.add(
            Order(
                customer_identity_id=other_customer.id,
                household_id=seed.household_id,
                status="awaiting_payment",
                currency="IRR",
                merchandise_total_irr=seed.offer_price_irr,
                checkout_idempotency_key=f"capacity-blocker-{seed.token}",
                delivery_address_snapshot={"line": "blocker"},
            )
        )
        await session.flush()
        blocker_order = await session.scalar(
            select(Order).where(Order.checkout_idempotency_key == f"capacity-blocker-{seed.token}")
        )
        assert blocker_order is not None
        session.add(
            OrderLine(
                order_id=blocker_order.id,
                offer_id=seed.offer_id,
                sku_snapshot=f"RESERVE-{seed.token}",
                title_fa_snapshot="blocker",
                unit_label_fa_snapshot="عدد",
                supplier_country_snapshot="FR",
                quantity=1,
                unit_price_irr=seed.offer_price_irr,
                line_total_irr=seed.offer_price_irr,
                created_at=utc_now(),
            )
        )
        await session.commit()

    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id, with_for_update=True)
        offer = await session.get(Offer, seed.offer_id)
        supplier = await session.get(Supplier, offer.supplier_id) if offer else None
        address = await session.get(HouseholdAddress, seed.address_id)
        assert reservation is not None and offer is not None and supplier is not None
        assert address is not None
        with pytest.raises(ReservationError, match="offer_capacity_exhausted"):
            await approve_and_convert_reservation(
                session,
                reservation=reservation,
                offer=offer,
                supplier=supplier,
                address=address,
                customer_identity_id=seed.customer_id,
            )
        await session.rollback()


async def test_approve_rejects_an_address_from_another_household() -> None:
    seed = await _seed_reservable_offer()
    reservation_id = await _request(seed)
    await _propose(seed, reservation_id, reconfirmed_price_irr=8_500_000)
    async with SessionFactory() as session:
        foreign_household = Household(name=f"hh-foreign-{seed.token}")
        session.add(foreign_household)
        await session.flush()
        foreign_address = HouseholdAddress(
            household_id=foreign_household.id,
            label="خانه",
            recipient_name="دیگری",
            recipient_mobile_e164="+989121111111",
            province="تهران",
            city="تهران",
            address_line="جای دیگر",
            active=True,
        )
        session.add(foreign_address)
        await session.commit()
        foreign_address_id = foreign_address.id

    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id, with_for_update=True)
        offer = await session.get(Offer, seed.offer_id)
        supplier = await session.get(Supplier, offer.supplier_id) if offer else None
        address = await session.get(HouseholdAddress, foreign_address_id)
        assert reservation is not None and offer is not None and supplier is not None
        assert address is not None
        with pytest.raises(ReservationError):
            await approve_and_convert_reservation(
                session,
                reservation=reservation,
                offer=offer,
                supplier=supplier,
                address=address,
                customer_identity_id=seed.customer_id,
            )


# --- expiry ----------------------------------------------------------------


async def test_response_after_the_deadline_expires_instead_of_approving() -> None:
    seed = await _seed_reservable_offer()
    reservation_id = await _request(seed)
    await _propose(seed, reservation_id, reconfirmed_price_irr=8_500_000, response_window_hours=0)
    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id, with_for_update=True)
        offer = await session.get(Offer, seed.offer_id)
        supplier = await session.get(Supplier, offer.supplier_id) if offer else None
        address = await session.get(HouseholdAddress, seed.address_id)
        assert reservation is not None and offer is not None and supplier is not None
        assert address is not None
        with pytest.raises(ReservationError, match="expired"):
            await approve_and_convert_reservation(
                session,
                reservation=reservation,
                offer=offer,
                supplier=supplier,
                address=address,
                customer_identity_id=seed.customer_id,
            )
        await session.commit()
    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id)
    assert reservation is not None and reservation.status == "expired"


async def test_expiry_sweep_expires_stale_requested_and_proposed_reservations() -> None:
    fresh_seed = await _seed_reservable_offer()
    stale_requested_seed = await _seed_reservable_offer()
    stale_proposed_seed = await _seed_reservable_offer()

    fresh_id = await _request(fresh_seed)
    stale_requested_id = await _request(stale_requested_seed)
    stale_proposed_id = await _request(stale_proposed_seed)
    await _propose(stale_proposed_seed, stale_proposed_id, reconfirmed_price_irr=8_500_000)

    now = utc_now()
    async with SessionFactory() as session:
        stale_requested = await session.get(Reservation, stale_requested_id, with_for_update=True)
        stale_proposed = await session.get(Reservation, stale_proposed_id, with_for_update=True)
        assert stale_requested is not None and stale_proposed is not None
        stale_requested.operator_review_by = now - timedelta(hours=1)
        stale_proposed.customer_respond_by = now - timedelta(hours=1)
        await session.commit()

    counts = await expire_stale_reservations(SessionFactory)
    assert counts["review_expired"] >= 1
    assert counts["response_expired"] >= 1

    async with SessionFactory() as session:
        fresh = await session.get(Reservation, fresh_id)
        stale_requested = await session.get(Reservation, stale_requested_id)
        stale_proposed = await session.get(Reservation, stale_proposed_id)
    assert fresh is not None and fresh.status == "requested"
    assert stale_requested is not None and stale_requested.status == "expired"
    assert stale_proposed is not None and stale_proposed.status == "expired"


# --- concurrency: approve vs. decline --------------------------------------


async def _race_approve(
    seed: ReservationSeed, reservation_id: uuid.UUID, *, delay: float = 0.0
) -> str:
    if delay:
        await asyncio.sleep(delay)
    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id, with_for_update=True)
        offer = await session.get(Offer, seed.offer_id)
        supplier = await session.get(Supplier, offer.supplier_id) if offer else None
        address = await session.get(HouseholdAddress, seed.address_id)
        assert reservation is not None and offer is not None and supplier is not None
        assert address is not None
        try:
            await approve_and_convert_reservation(
                session,
                reservation=reservation,
                offer=offer,
                supplier=supplier,
                address=address,
                customer_identity_id=seed.customer_id,
            )
        except ReservationError:
            await session.rollback()
            return "rejected"
        await session.commit()
        return "converted"


async def _race_decline(
    seed: ReservationSeed, reservation_id: uuid.UUID, *, delay: float = 0.0
) -> str:
    if delay:
        await asyncio.sleep(delay)
    async with SessionFactory() as session:
        reservation = await session.get(Reservation, reservation_id, with_for_update=True)
        assert reservation is not None
        try:
            await decline_reservation(
                session,
                reservation=reservation,
                customer_identity_id=seed.customer_id,
                reason="race test",
            )
        except ReservationError:
            await session.rollback()
            return "rejected"
        await session.commit()
        return "declined"


async def test_concurrent_approve_and_decline_never_both_succeed() -> None:
    # approve does several preliminary queries (offer, supplier, address)
    # before it ever reaches the contended Reservation row, while decline
    # locks that row on its very first query -- with zero handicap, decline
    # would structurally win every trial and the "approve wins" branch of
    # the invariant below would never actually run. Alternating a small
    # head start forces both lock-acquisition orderings to occur, while
    # both tasks still run concurrently via asyncio.gather and genuinely
    # contend for the same row in Postgres.
    approve_wins = 0
    decline_wins = 0
    for trial in range(10):
        seed = await _seed_reservable_offer()
        reservation_id = await _request(seed)
        await _propose(seed, reservation_id, reconfirmed_price_irr=8_500_000)

        give_approve_a_head_start = trial % 2 == 0
        approve_result, decline_result = await asyncio.gather(
            _race_approve(seed, reservation_id, delay=0.0 if give_approve_a_head_start else 0.05),
            _race_decline(seed, reservation_id, delay=0.05 if give_approve_a_head_start else 0.0),
        )
        outcomes = {approve_result, decline_result}
        assert outcomes in ({"converted", "rejected"}, {"declined", "rejected"})
        if approve_result == "converted":
            approve_wins += 1
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
        reservation_status = None
        async with SessionFactory() as session:
            reservation = await session.get(Reservation, reservation_id)
            reservation_status = reservation.status if reservation else None
        if reservation_status == "converted":
            assert order_count == 1
        else:
            assert reservation_status == "customer_declined"
            assert order_count == 0

    assert approve_wins > 0
    assert decline_wins > 0


# --- HTTP layer: gating ------------------------------------------------------


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def test_http_reserve_now_endpoints_are_disabled_by_default(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_reservable_offer()
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer

    assert get_settings().reserve_now_enabled is False

    create_response = await client.post(
        "/api/v1/reservations",
        json={
            "household_id": str(seed.household_id),
            "offer_id": str(seed.offer_id),
            "quantity": 1,
        },
        headers={"Idempotency-Key": f"gate-{uuid.uuid4().hex}"},
    )
    list_response = await client.get("/api/v1/reservations")
    assert create_response.status_code == 409
    assert create_response.json()["error"]["code"] == "reserve_now_disabled"
    assert list_response.status_code == 409
    assert list_response.json()["error"]["code"] == "reserve_now_disabled"


# --- HTTP layer: full lifecycle ---------------------------------------------


async def test_http_full_reserve_now_lifecycle(
    reserve_now_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_reservable_offer(offer_price_irr=8_000_000)
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, seed.customer_id)
        operator = await session.get(AuthIdentity, seed.operator_id)

    app.dependency_overrides[get_current_identity] = lambda: customer
    created = await client.post(
        "/api/v1/reservations",
        json={
            "household_id": str(seed.household_id),
            "offer_id": str(seed.offer_id),
            "quantity": 1,
        },
        headers={"Idempotency-Key": f"lifecycle-{uuid.uuid4().hex}"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "requested"
    assert body["deposit_charged_irr"] == 0
    reservation_id = body["id"]

    app.dependency_overrides[get_current_identity] = lambda: operator
    proposed = await client.post(
        f"/api/v1/operator/reservations/{reservation_id}/reconfirm-and-propose",
        json={
            "reconfirmed_price_irr": 8_200_000,
            "reconfirmed_available": True,
            "reason": "قیمت با تامین‌کننده تایید شد",
        },
    )
    assert proposed.status_code == 200
    assert proposed.json()["status"] == "proposed"

    app.dependency_overrides[get_current_identity] = lambda: customer
    approved = await client.post(
        f"/api/v1/reservations/{reservation_id}/approve",
        json={"address_id": str(seed.address_id)},
    )
    assert approved.status_code == 200
    order_body = approved.json()
    assert order_body["status"] == "awaiting_payment"
    assert order_body["merchandise_total_irr"] == 8_200_000


async def test_http_reservation_is_non_enumerating_for_a_foreign_customer(
    reserve_now_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_reservable_offer()
    reservation_id = await _request(seed)
    async with SessionFactory() as session:
        other_customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98917{seed.token[:7]}", status="active"
        )
        session.add(other_customer)
        await session.commit()
        other_id = other_customer.id
    async with SessionFactory() as session:
        other_customer_obj = await session.get(AuthIdentity, other_id)
    app.dependency_overrides[get_current_identity] = lambda: other_customer_obj

    nonexistent = await client.get(f"/api/v1/reservations/{uuid.uuid4()}")
    foreign = await client.get(f"/api/v1/reservations/{reservation_id}")
    assert nonexistent.status_code == foreign.status_code == 404
    assert nonexistent.json()["error"]["code"] == foreign.json()["error"]["code"]
