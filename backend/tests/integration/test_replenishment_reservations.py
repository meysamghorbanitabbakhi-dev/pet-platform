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
from app.modules.food_estimation.models import FoodEstimate
from app.modules.households.models import Household, HouseholdAddress, HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.inventory.models import InventoryUnit
from app.modules.orders.models import Order
from app.modules.payments.models import PaymentAttempt
from app.modules.replenishment.models import ReplenishmentReservation
from app.modules.replenishment.reservations import (
    ReplenishmentReservationError,
    approve_reservation,
    create_or_refresh_reservation_for_unit,
    decline_reservation,
    expire_stale_reservations,
    invalidate_reservation_for_unit,
    scan_and_create_due_reservations,
)
from app.modules.system.models import OperatorAuditLog
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
def replenishment_reservation_enabled() -> Iterator[None]:
    settings = get_settings()
    settings.replenishment_reservation_enabled = True
    try:
        yield
    finally:
        settings.replenishment_reservation_enabled = False


@dataclass(slots=True)
class ReplenishmentSeed:
    token: str
    customer_id: uuid.UUID
    household_id: uuid.UUID
    address_id: uuid.UUID
    product_id: uuid.UUID
    offer_id: uuid.UUID
    offer_price_irr: int
    unit_id: uuid.UUID
    estimate_id: uuid.UUID


async def _seed_unit_with_estimate(
    *,
    low_days: int = 5,
    high_days: int = 8,
    offer_price_irr: int = 900_000,
    offer_status: str = "active",
) -> ReplenishmentSeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98919{token[:7]}", status="active"
        )
        supplier = Supplier(
            internal_name=f"replen-supplier-{token}", country_code="DE", active=True
        )
        product = Product(name_fa=f"محصول تمدید {token}", status="active")
        household = Household(name=f"hh-replen-{token}")
        session.add_all([customer, supplier, product, household])
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
            sku=f"REPLEN-{token}",
            title_fa=f"پیشنهاد تمدید {token}",
            unit_label_fa="عدد",
            price_irr=offer_price_irr,
            status=offer_status,
            stock_posture="sourced_after_payment",
            sourcing_capacity_status="open",
            sourcing_route="individual",
            minimum_shelf_life_months=6,
        )
        unit = InventoryUnit(
            household_id=household.id,
            product_id=product.id,
            source="platform_order",
            state="opened",
            label=f"unit-{token}",
            initial_quantity_grams=3000,
            remaining_quantity_grams=1000,
            opened_at=utc_now(),
        )
        session.add_all([address, offer, unit])
        await session.flush()
        estimate = FoodEstimate(
            inventory_unit_id=unit.id,
            low_days=low_days,
            high_days=high_days,
            confidence="medium",
            status="active",
            calculated_at=utc_now(),
            basis="owner_confirmed_portion",
        )
        session.add(estimate)
        await session.commit()
        return ReplenishmentSeed(
            token=token,
            customer_id=customer.id,
            household_id=household.id,
            address_id=address.id,
            product_id=product.id,
            offer_id=offer.id,
            offer_price_irr=offer_price_irr,
            unit_id=unit.id,
            estimate_id=estimate.id,
        )


async def _reservation_count(unit_id: uuid.UUID) -> int:
    async with SessionFactory() as session:
        return len(
            (
                await session.scalars(
                    select(ReplenishmentReservation).where(
                        ReplenishmentReservation.inventory_unit_id == unit_id
                    )
                )
            ).all()
        )


async def _create(seed: ReplenishmentSeed) -> uuid.UUID | None:
    async with SessionFactory() as session:
        unit = await session.scalar(
            select(InventoryUnit).where(InventoryUnit.id == seed.unit_id).with_for_update()
        )
        assert unit is not None
        reservation = await create_or_refresh_reservation_for_unit(session, unit=unit)
        await session.commit()
        return reservation.id if reservation else None


# --- service-level: creation, dedup, refresh --------------------------------


async def test_create_creates_when_within_lead_days_and_offer_available() -> None:
    seed = await _seed_unit_with_estimate(low_days=5, high_days=8)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        reservation = await session.get(ReplenishmentReservation, reservation_id)
    assert reservation is not None
    assert reservation.status == "pending_approval"
    assert reservation.predicted_depletion_low_days == 5
    assert reservation.predicted_depletion_high_days == 8
    assert reservation.offer_id == seed.offer_id
    assert reservation.source_food_estimate_id == seed.estimate_id
    assert reservation.approval_expires_at > utc_now() + timedelta(hours=47)


async def test_create_returns_none_beyond_lead_days() -> None:
    seed = await _seed_unit_with_estimate(low_days=20, high_days=25)
    assert await _create(seed) is None


async def test_create_returns_none_without_available_offer() -> None:
    seed = await _seed_unit_with_estimate(low_days=5, offer_status="unavailable")
    assert await _create(seed) is None


async def test_create_returns_none_when_the_product_is_inactive() -> None:
    """_find_available_offer uses the shared catalog eligibility policy
    (app.modules.catalog.eligibility) -- a reorderable-looking offer whose
    product has since been deactivated must never be auto-recommended."""
    seed = await _seed_unit_with_estimate(low_days=5)
    async with SessionFactory() as session:
        product = await session.get(Product, seed.product_id)
        assert product is not None
        product.status = "retired"
        await session.commit()
    assert await _create(seed) is None


async def test_create_returns_none_when_the_supplier_is_inactive() -> None:
    seed = await _seed_unit_with_estimate(low_days=5)
    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        supplier = await session.get(Supplier, offer.supplier_id)
        assert supplier is not None
        supplier.active = False
        await session.commit()
    assert await _create(seed) is None


async def test_create_returns_none_outside_the_offers_sale_window() -> None:
    seed = await _seed_unit_with_estimate(low_days=5)
    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        offer.available_from = utc_now() + timedelta(days=1)
        await session.commit()
    assert await _create(seed) is None


async def test_create_returns_none_without_active_estimate() -> None:
    seed = await _seed_unit_with_estimate(low_days=5)
    async with SessionFactory() as session:
        estimate = await session.get(FoodEstimate, seed.estimate_id)
        assert estimate is not None
        estimate.status = "corrected"
        await session.commit()
    assert await _create(seed) is None


async def test_create_does_not_duplicate_on_repeat_calls() -> None:
    seed = await _seed_unit_with_estimate(low_days=5)
    first_id = await _create(seed)
    second_id = await _create(seed)
    assert first_id is not None
    assert first_id == second_id
    assert await _reservation_count(seed.unit_id) == 1


async def test_create_refreshes_pending_reservation_in_place_on_worsened_estimate() -> None:
    seed = await _seed_unit_with_estimate(low_days=10, high_days=12)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        reservation = await session.get(ReplenishmentReservation, reservation_id)
        assert reservation is not None
        original_deadline = reservation.approval_expires_at
        old_estimate = await session.get(FoodEstimate, seed.estimate_id)
        assert old_estimate is not None
        old_estimate.status = "corrected"
        new_estimate = FoodEstimate(
            inventory_unit_id=seed.unit_id,
            low_days=3,
            high_days=4,
            confidence="medium",
            status="active",
            calculated_at=utc_now(),
            basis="owner_confirmed_portion",
        )
        session.add(new_estimate)
        await session.commit()
        new_estimate_id = new_estimate.id

    refreshed_id = await _create(seed)
    assert refreshed_id == reservation_id
    assert await _reservation_count(seed.unit_id) == 1
    async with SessionFactory() as session:
        reservation = await session.get(ReplenishmentReservation, reservation_id)
    assert reservation is not None
    assert reservation.predicted_depletion_low_days == 3
    assert reservation.predicted_depletion_high_days == 4
    assert reservation.source_food_estimate_id == new_estimate_id
    # The approval clock does not restart on refresh.
    assert reservation.approval_expires_at == original_deadline


async def test_create_leaves_a_terminal_reservation_alone() -> None:
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        reservation = await session.get(
            ReplenishmentReservation, reservation_id, with_for_update=True
        )
        assert reservation is not None
        await decline_reservation(
            session,
            reservation=reservation,
            customer_identity_id=seed.customer_id,
            reason="test",
        )
        await session.commit()
    # Even a fresh, still-qualifying estimate must not resurrect a resolved
    # reservation -- one reservation per unit, ever.
    again_id = await _create(seed)
    assert again_id == reservation_id
    assert await _reservation_count(seed.unit_id) == 1
    async with SessionFactory() as session:
        reservation = await session.get(ReplenishmentReservation, reservation_id)
    assert reservation is not None and reservation.status == "declined"


# --- service-level: approve --------------------------------------------------


async def test_approve_creates_a_real_order_at_the_live_offer_price() -> None:
    seed = await _seed_unit_with_estimate(low_days=5, offer_price_irr=1_200_000)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        reservation = await session.get(
            ReplenishmentReservation, reservation_id, with_for_update=True
        )
        assert reservation is not None
        reservation, order = await approve_reservation(
            session,
            reservation=reservation,
            customer_identity_id=seed.customer_id,
            address_id=seed.address_id,
        )
    assert order.status == "awaiting_payment"
    assert order.merchandise_total_irr == 1_200_000
    assert reservation.status == "approved"
    assert reservation.resulting_order_id == order.id
    assert reservation.approved_at is not None


async def test_crash_between_order_creation_and_reservation_approval_leaves_no_orphan() -> None:
    """Fault injection (Workstream 2): simulates a process crash after the
    order is constructed but before approve_reservation's own atomic
    commit -- create_order_uncommitted must leave nothing persisted when
    the caller never reaches its own commit, and a subsequent real
    approval attempt must succeed cleanly from scratch rather than
    tripping over an orphaned half-written order."""
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    idempotency_key = f"replenishment:{reservation_id}"

    async with SessionFactory() as session:
        reservation = await session.get(
            ReplenishmentReservation, reservation_id, with_for_update=True
        )
        assert reservation is not None
        # Exactly what approve_reservation does internally, up to (but not
        # including) mutating reservation.status and committing -- then we
        # deliberately stop here, simulating the process dying right at
        # that point, instead of continuing to the atomic commit.
        await CheckoutService().create_order_uncommitted(
            session,
            customer_identity_id=seed.customer_id,
            household_id=seed.household_id,
            address_id=seed.address_id,
            items=[CheckoutItem(seed.offer_id, 1)],
            idempotency_key=idempotency_key,
            allowed_modes=frozenset({"full_payment"}),
        )
        await session.rollback()

    async with SessionFactory() as session:
        orphan = await session.scalar(
            select(Order).where(
                Order.customer_identity_id == seed.customer_id,
                Order.checkout_idempotency_key == idempotency_key,
            )
        )
        assert orphan is None
        untouched = await session.get(ReplenishmentReservation, reservation_id)
        assert untouched is not None and untouched.status == "pending_approval"

    # A real, subsequent approval attempt (the customer retrying, or the
    # same request replayed) must succeed cleanly -- no leftover state
    # from the simulated crash blocks it.
    async with SessionFactory() as session:
        reservation = await session.get(
            ReplenishmentReservation, reservation_id, with_for_update=True
        )
        assert reservation is not None
        reservation, order = await approve_reservation(
            session,
            reservation=reservation,
            customer_identity_id=seed.customer_id,
            address_id=seed.address_id,
        )
    assert reservation.status == "approved"
    assert order.checkout_idempotency_key == idempotency_key


async def test_approve_does_not_auto_charge() -> None:
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        reservation = await session.get(
            ReplenishmentReservation, reservation_id, with_for_update=True
        )
        assert reservation is not None
        _, order = await approve_reservation(
            session,
            reservation=reservation,
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


async def test_approve_is_idempotent_and_returns_the_same_order() -> None:
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None

    async def _approve_once() -> uuid.UUID:
        async with SessionFactory() as session:
            reservation = await session.get(
                ReplenishmentReservation, reservation_id, with_for_update=True
            )
            assert reservation is not None
            _, order = await approve_reservation(
                session,
                reservation=reservation,
                customer_identity_id=seed.customer_id,
                address_id=seed.address_id,
            )
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


async def test_approve_after_deadline_expires_instead_of_approving() -> None:
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        reservation = await session.get(
            ReplenishmentReservation, reservation_id, with_for_update=True
        )
        assert reservation is not None
        reservation.approval_expires_at = utc_now() - timedelta(hours=1)
        await session.commit()
    async with SessionFactory() as session:
        reservation = await session.get(
            ReplenishmentReservation, reservation_id, with_for_update=True
        )
        assert reservation is not None
        with pytest.raises(ReplenishmentReservationError, match="expired"):
            await approve_reservation(
                session,
                reservation=reservation,
                customer_identity_id=seed.customer_id,
                address_id=seed.address_id,
            )
    async with SessionFactory() as session:
        reservation = await session.get(ReplenishmentReservation, reservation_id)
    assert reservation is not None and reservation.status == "expired"


# --- service-level: decline --------------------------------------------------


async def test_decline_sets_declined() -> None:
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        reservation = await session.get(
            ReplenishmentReservation, reservation_id, with_for_update=True
        )
        assert reservation is not None
        result = await decline_reservation(
            session,
            reservation=reservation,
            customer_identity_id=seed.customer_id,
            reason="کافی است",
        )
        await session.commit()
    assert result.status == "declined"
    assert result.declined_at is not None


async def test_decline_is_idempotent() -> None:
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None

    async def _decline_once() -> ReplenishmentReservation:
        async with SessionFactory() as session:
            reservation = await session.get(
                ReplenishmentReservation, reservation_id, with_for_update=True
            )
            assert reservation is not None
            result = await decline_reservation(
                session,
                reservation=reservation,
                customer_identity_id=seed.customer_id,
                reason=None,
            )
            await session.commit()
            return result

    first = await _decline_once()
    second = await _decline_once()
    assert first.declined_at == second.declined_at


# --- service-level: invalidation ---------------------------------------------


async def test_invalidate_sets_invalidated_when_pending() -> None:
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        result = await invalidate_reservation_for_unit(
            session, inventory_unit_id=seed.unit_id, reason="inventory_exhausted"
        )
        await session.commit()
    assert result is not None
    assert result.status == "invalidated"
    assert result.invalidated_at is not None


async def test_invalidate_leaves_an_approved_reservation_alone() -> None:
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        reservation = await session.get(
            ReplenishmentReservation, reservation_id, with_for_update=True
        )
        assert reservation is not None
        await approve_reservation(
            session,
            reservation=reservation,
            customer_identity_id=seed.customer_id,
            address_id=seed.address_id,
        )
    async with SessionFactory() as session:
        result = await invalidate_reservation_for_unit(
            session, inventory_unit_id=seed.unit_id, reason="inventory_exhausted"
        )
        await session.commit()
    assert result is not None and result.status == "approved"


async def test_invalidate_returns_none_when_no_reservation_exists() -> None:
    seed = await _seed_unit_with_estimate(low_days=20, high_days=25)
    async with SessionFactory() as session:
        result = await invalidate_reservation_for_unit(
            session, inventory_unit_id=seed.unit_id, reason="inventory_exhausted"
        )
    assert result is None


# --- expiry sweep and scheduler scan -----------------------------------------


async def test_expire_stale_reservations_expires_past_deadline_only() -> None:
    fresh_seed = await _seed_unit_with_estimate(low_days=5)
    stale_seed = await _seed_unit_with_estimate(low_days=5)
    fresh_id = await _create(fresh_seed)
    stale_id = await _create(stale_seed)
    assert fresh_id is not None and stale_id is not None

    async with SessionFactory() as session:
        stale = await session.get(ReplenishmentReservation, stale_id, with_for_update=True)
        assert stale is not None
        stale.approval_expires_at = utc_now() - timedelta(hours=1)
        await session.commit()

    expired_count = await expire_stale_reservations(SessionFactory)
    assert expired_count >= 1

    async with SessionFactory() as session:
        fresh = await session.get(ReplenishmentReservation, fresh_id)
        stale = await session.get(ReplenishmentReservation, stale_id)
    assert fresh is not None and fresh.status == "pending_approval"
    assert stale is not None and stale.status == "expired"
    assert stale.reminder_sent_at is not None


async def test_scan_creates_for_qualifying_units_only() -> None:
    # batch_size is generous: other suites in this shared test database can
    # leave their own qualifying (state='opened', low_days<=lead_days) units
    # behind, and the scan has no per-test scoping -- a small limit would
    # make this test flaky depending on unrelated leftover rows sorting
    # ahead of this test's own unit.
    qualifying = await _seed_unit_with_estimate(low_days=5, high_days=8)
    not_yet = await _seed_unit_with_estimate(low_days=25, high_days=30)
    counts = await scan_and_create_due_reservations(SessionFactory, batch_size=10_000)
    assert counts["created"] >= 1
    assert await _reservation_count(qualifying.unit_id) == 1
    assert await _reservation_count(not_yet.unit_id) == 0


async def test_scan_refreshes_rather_than_duplicates_on_second_run() -> None:
    seed = await _seed_unit_with_estimate(low_days=5, high_days=8)
    first_counts = await scan_and_create_due_reservations(SessionFactory, batch_size=10_000)
    assert first_counts["created"] >= 1
    second_counts = await scan_and_create_due_reservations(SessionFactory, batch_size=10_000)
    assert second_counts["created"] == 0
    assert await _reservation_count(seed.unit_id) == 1


# --- concurrency ---------------------------------------------------------


async def _race_create(seed: ReplenishmentSeed) -> uuid.UUID | None:
    async with SessionFactory() as session:
        unit = await session.scalar(
            select(InventoryUnit).where(InventoryUnit.id == seed.unit_id).with_for_update()
        )
        assert unit is not None
        reservation = await create_or_refresh_reservation_for_unit(session, unit=unit)
        await session.commit()
        return reservation.id if reservation else None


async def test_concurrent_creation_attempts_never_produce_two_rows() -> None:
    for _ in range(5):
        seed = await _seed_unit_with_estimate(low_days=5, high_days=8)
        first_id, second_id = await asyncio.gather(_race_create(seed), _race_create(seed))
        assert first_id is not None and second_id is not None
        assert first_id == second_id
        assert await _reservation_count(seed.unit_id) == 1


async def _race_approve(
    seed: ReplenishmentSeed, reservation_id: uuid.UUID, *, delay: float = 0.0
) -> str:
    if delay:
        await asyncio.sleep(delay)
    async with SessionFactory() as session:
        reservation = await session.get(
            ReplenishmentReservation, reservation_id, with_for_update=True
        )
        assert reservation is not None
        try:
            await approve_reservation(
                session,
                reservation=reservation,
                customer_identity_id=seed.customer_id,
                address_id=seed.address_id,
            )
        except ReplenishmentReservationError:
            await session.rollback()
            return "rejected"
        return "approved"


async def _race_decline(
    seed: ReplenishmentSeed, reservation_id: uuid.UUID, *, delay: float = 0.0
) -> str:
    if delay:
        await asyncio.sleep(delay)
    async with SessionFactory() as session:
        reservation = await session.get(
            ReplenishmentReservation, reservation_id, with_for_update=True
        )
        assert reservation is not None
        try:
            await decline_reservation(
                session,
                reservation=reservation,
                customer_identity_id=seed.customer_id,
                reason="race test",
            )
        except ReplenishmentReservationError:
            await session.rollback()
            return "rejected"
        await session.commit()
        return "declined"


async def test_concurrent_approve_and_decline_never_both_succeed() -> None:
    approve_wins = 0
    decline_wins = 0
    for trial in range(10):
        seed = await _seed_unit_with_estimate(low_days=5)
        reservation_id = await _create(seed)
        assert reservation_id is not None

        give_approve_a_head_start = trial % 2 == 0
        approve_result, decline_result = await asyncio.gather(
            _race_approve(seed, reservation_id, delay=0.0 if give_approve_a_head_start else 0.05),
            _race_decline(seed, reservation_id, delay=0.05 if give_approve_a_head_start else 0.0),
        )
        outcomes = {approve_result, decline_result}
        assert outcomes in ({"approved", "rejected"}, {"declined", "rejected"})
        if approve_result == "approved":
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
        async with SessionFactory() as session:
            reservation = await session.get(ReplenishmentReservation, reservation_id)
            reservation_status = reservation.status if reservation else None
        if reservation_status == "approved":
            assert order_count == 1
        else:
            assert reservation_status == "declined"
            assert order_count == 0

    assert approve_wins > 0
    assert decline_wins > 0


# --- HTTP layer: gating -------------------------------------------------------


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def test_http_replenishment_reservation_endpoints_are_disabled_by_default(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_unit_with_estimate(low_days=5)
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer

    assert get_settings().replenishment_reservation_enabled is False

    list_response = await client.get(
        f"/api/v1/pet-life/households/{seed.household_id}/replenishment-reservations"
    )
    assert list_response.status_code == 409
    assert list_response.json()["error"]["code"] == "replenishment_reservation_disabled"

    detail_response = await client.get(
        f"/api/v1/pet-life/replenishment-reservations/{uuid.uuid4()}"
    )
    assert detail_response.status_code == 409
    assert detail_response.json()["error"]["code"] == "replenishment_reservation_disabled"


# --- HTTP layer: full lifecycle ------------------------------------------------


async def test_http_full_replenishment_reservation_lifecycle(
    replenishment_reservation_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_unit_with_estimate(low_days=5, offer_price_irr=1_500_000)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer

    listed = await client.get(
        f"/api/v1/pet-life/households/{seed.household_id}/replenishment-reservations"
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == str(reservation_id)

    detail = await client.get(f"/api/v1/pet-life/replenishment-reservations/{reservation_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "pending_approval"
    assert detail.json()["auto_charged"] is False

    approved = await client.post(
        f"/api/v1/pet-life/replenishment-reservations/{reservation_id}/approve",
        json={"address_id": str(seed.address_id)},
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved"
    assert body["resulting_order_id"] is not None

    async with SessionFactory() as session:
        order = await session.get(Order, uuid.UUID(body["resulting_order_id"]))
    assert order is not None
    assert order.status == "awaiting_payment"
    assert order.merchandise_total_irr == 1_500_000


async def test_http_decline_replenishment_reservation(
    replenishment_reservation_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer

    declined = await client.post(
        f"/api/v1/pet-life/replenishment-reservations/{reservation_id}/decline",
        json={"reason": "دیگر لازم نیست"},
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"


async def test_http_replenishment_reservation_is_non_enumerating_for_a_foreign_household(
    replenishment_reservation_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
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

    nonexistent = await client.get(f"/api/v1/pet-life/replenishment-reservations/{uuid.uuid4()}")
    foreign = await client.get(f"/api/v1/pet-life/replenishment-reservations/{reservation_id}")
    assert nonexistent.status_code == foreign.status_code == 404
    assert nonexistent.json()["error"]["code"] == foreign.json()["error"]["code"]


# --- HTTP layer: correct_estimate / exhaust_inventory hooks -------------------


async def test_http_correct_estimate_refreshes_pending_reservation(
    replenishment_reservation_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_unit_with_estimate(low_days=10, high_days=12)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer

    corrected = await client.post(
        f"/api/v1/pet-life/inventory/{seed.unit_id}/estimate/correct",
        json={"remaining_grams": 400, "daily_portion_grams": 100},
    )
    assert corrected.status_code == 200

    assert await _reservation_count(seed.unit_id) == 1
    async with SessionFactory() as session:
        reservation = await session.get(ReplenishmentReservation, reservation_id)
    assert reservation is not None
    assert reservation.status == "pending_approval"
    assert reservation.predicted_depletion_low_days == 4


async def test_http_exhaust_inventory_invalidates_pending_reservation(
    replenishment_reservation_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer

    exhausted = await client.post(f"/api/v1/pet-life/inventory/{seed.unit_id}/exhaust")
    assert exhausted.status_code == 204

    async with SessionFactory() as session:
        reservation = await session.get(ReplenishmentReservation, reservation_id)
    assert reservation is not None
    assert reservation.status == "invalidated"
    assert reservation.invalidated_at is not None


# --- HTTP layer: operator monitoring and correction (Workstream 4) -----------


async def _seed_operator() -> AuthIdentity:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98929{token[:7]}", status="active"
        )
        session.add(operator)
        await session.commit()
        return operator


async def test_http_operator_replenishment_routes_are_disabled_by_default(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    operator = await _seed_operator()
    app.dependency_overrides[get_current_identity] = lambda: operator

    assert get_settings().replenishment_reservation_enabled is False
    listed = await client.get("/api/v1/operator/replenishment-reservations")
    assert listed.status_code == 409
    detail = await client.get(f"/api/v1/operator/replenishment-reservations/{uuid.uuid4()}")
    assert detail.status_code == 409
    invalidated = await client.post(
        f"/api/v1/operator/replenishment-reservations/{uuid.uuid4()}/invalidate",
        json={"reason": "should not reach this while disabled"},
    )
    assert invalidated.status_code == 409


async def test_http_operator_can_list_and_view_reservation_detail(
    replenishment_reservation_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    operator = await _seed_operator()
    app.dependency_overrides[get_current_identity] = lambda: operator

    listed = await client.get(
        "/api/v1/operator/replenishment-reservations", params={"status": "pending_approval"}
    )
    assert listed.status_code == 200
    assert str(reservation_id) in {item["id"] for item in listed.json()}

    detail = await client.get(f"/api/v1/operator/replenishment-reservations/{reservation_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == str(reservation_id)
    assert body["status"] == "pending_approval"
    assert [event["event_type"] for event in body["events"]] == ["created"]

    missing = await client.get(f"/api/v1/operator/replenishment-reservations/{uuid.uuid4()}")
    assert missing.status_code == 404


async def test_http_operator_can_invalidate_a_pending_reservation(
    replenishment_reservation_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    operator = await _seed_operator()
    app.dependency_overrides[get_current_identity] = lambda: operator

    response = await client.post(
        f"/api/v1/operator/replenishment-reservations/{reservation_id}/invalidate",
        json={"reason": "estimate mapping looked wrong on manual review"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "invalidated"

    # Idempotent: invalidating an already-invalidated reservation is a
    # no-op success, not an error or a duplicate audit entry.
    again = await client.post(
        f"/api/v1/operator/replenishment-reservations/{reservation_id}/invalidate",
        json={"reason": "retry after a client timeout"},
    )
    assert again.status_code == 200
    assert again.json()["status"] == "invalidated"

    async with SessionFactory() as session:
        audit_count = len(
            (
                await session.scalars(
                    select(OperatorAuditLog).where(
                        OperatorAuditLog.action == "replenishment_reservation.invalidated",
                        OperatorAuditLog.resource_id == str(reservation_id),
                    )
                )
            ).all()
        )
    assert audit_count == 1

    # A subsequent customer approval attempt against the now-invalidated
    # reservation must fail, not silently create an order.
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer
    approved = await client.post(
        f"/api/v1/pet-life/replenishment-reservations/{reservation_id}/approve",
        json={"address_id": str(seed.address_id)},
    )
    assert approved.status_code == 409


async def test_http_operator_cannot_invalidate_an_already_approved_reservation(
    replenishment_reservation_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        reservation = await session.get(
            ReplenishmentReservation, reservation_id, with_for_update=True
        )
        assert reservation is not None
        await approve_reservation(
            session,
            reservation=reservation,
            customer_identity_id=seed.customer_id,
            address_id=seed.address_id,
        )
    operator = await _seed_operator()
    app.dependency_overrides[get_current_identity] = lambda: operator

    response = await client.post(
        f"/api/v1/operator/replenishment-reservations/{reservation_id}/invalidate",
        json={"reason": "should be rejected: already approved"},
    )
    assert response.status_code == 409


async def test_http_operator_replenishment_routes_require_operator_role(
    replenishment_reservation_enabled: None,
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    app, client = app_and_client
    seed = await _seed_unit_with_estimate(low_days=5)
    reservation_id = await _create(seed)
    assert reservation_id is not None
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer

    listed = await client.get("/api/v1/operator/replenishment-reservations")
    assert listed.status_code == 403
    detail = await client.get(f"/api/v1/operator/replenishment-reservations/{reservation_id}")
    assert detail.status_code == 403
    invalidated = await client.post(
        f"/api/v1/operator/replenishment-reservations/{reservation_id}/invalidate",
        json={"reason": "a customer should never reach this"},
    )
    assert invalidated.status_code == 403
