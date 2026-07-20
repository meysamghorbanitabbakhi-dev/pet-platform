from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from app.db.session import SessionFactory, close_database
from app.modules.catalog.models import Offer, Product, Supplier
from app.modules.checkout.service import CheckoutError, CheckoutItem, CheckoutService
from app.modules.households.models import Household, HouseholdAddress, HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.orders.models import Order
from sqlalchemy import select

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL is required",
)


@pytest.fixture(autouse=True)
async def dispose_engine_between_event_loops() -> AsyncIterator[None]:
    yield
    await close_database()


@dataclass(slots=True)
class CapacitySeed:
    customer_id: uuid.UUID
    household_id: uuid.UUID
    address_id: uuid.UUID
    offer_id: uuid.UUID


@pytest.fixture()
async def capacity_seed() -> CapacitySeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98928{token[:7]}", status="active"
        )
        supplier = Supplier(
            internal_name=f"capacity-supplier-{token}", country_code="IR", active=True
        )
        product = Product(name_fa=f"capacity-product-{token}", status="active")
        household = Household(name=f"capacity-hh-{token}")
        session.add_all([customer, supplier, product, household])
        await session.flush()
        session.add(
            HouseholdMembership(household_id=household.id, identity_id=customer.id, role="owner")
        )
        address = HouseholdAddress(
            household_id=household.id,
            label="خانه",
            recipient_name="Test User",
            recipient_mobile_e164=customer.mobile_e164,
            province="Tehran",
            city="Tehran",
            address_line="capacity test address",
            postal_code=None,
            active=True,
        )
        # Only one unit of capacity ever available for this offer -- the
        # exact "last available unit" race the mission requires proving.
        offer = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"CAP-{token}",
            title_fa="ظرفیت محدود",
            unit_label_fa="عدد",
            price_irr=1_000_000,
            mode="full_payment",
            status="active",
            stock_posture="sourced_after_payment",
            sourcing_capacity_status="open",
            minimum_shelf_life_months=6,
            max_pending_quantity=1,
        )
        session.add_all([address, offer])
        await session.commit()
        return CapacitySeed(
            customer_id=customer.id,
            household_id=household.id,
            address_id=address.id,
            offer_id=offer.id,
        )


async def test_concurrent_checkout_for_the_last_available_unit_never_oversells(
    capacity_seed: CapacitySeed,
) -> None:
    """Two genuinely concurrent checkout attempts (real PostgreSQL row
    locking via CheckoutService.create_order's with_for_update(of=Offer),
    not a mock) race for an offer with max_pending_quantity=1. Exactly one
    must succeed; the other must be rejected as capacity-exhausted, never
    both succeeding and never both failing."""

    async def attempt(idempotency_key: str) -> str:
        async with SessionFactory() as session:
            try:
                await CheckoutService().create_order(
                    session,
                    customer_identity_id=capacity_seed.customer_id,
                    household_id=capacity_seed.household_id,
                    address_id=capacity_seed.address_id,
                    items=[CheckoutItem(capacity_seed.offer_id, 1)],
                    idempotency_key=idempotency_key,
                )
            except CheckoutError as exc:
                return f"rejected:{exc}"
            return "accepted"

    first, second = await asyncio.gather(
        attempt(f"capacity-race-a-{uuid.uuid4().hex}"),
        attempt(f"capacity-race-b-{uuid.uuid4().hex}"),
    )
    outcomes = {first, second}
    accepted_count = sum(1 for outcome in (first, second) if outcome == "accepted")
    rejected_count = sum(1 for outcome in (first, second) if outcome.startswith("rejected"))
    assert accepted_count == 1, outcomes
    assert rejected_count == 1, outcomes
    assert any("capacity" in outcome for outcome in outcomes if outcome.startswith("rejected"))

    async with SessionFactory() as session:
        orders = (
            await session.scalars(
                select(Order).where(
                    Order.customer_identity_id == capacity_seed.customer_id,
                    Order.household_id == capacity_seed.household_id,
                )
            )
        ).all()
    # Exactly one order was actually persisted -- the rejection above
    # happened before commit, not as an after-the-fact cleanup.
    assert len(orders) == 1


async def test_uncommitted_idempotency_race_does_not_destroy_the_callers_other_work(
    capacity_seed: CapacitySeed,
) -> None:
    """create_order_uncommitted participates in a trusted caller's own
    transaction (concierge acceptance, replenishment approval) rather than
    owning commit/rollback -- a genuine concurrent race on the same
    idempotency_key must be caught with a SAVEPOINT (begin_nested), not a
    plain session.rollback(), or the second racer's rollback would also
    discard whatever the caller already did earlier in that same
    transaction. Simulates that "caller's own prior work" with a marker
    Product row inserted before the checkout call, and proves it survives
    (commits successfully) regardless of which side of the race a given
    attempt landed on."""
    shared_key = f"trusted-caller-race-{uuid.uuid4().hex}"

    async def attempt(marker_name: str) -> tuple[str, uuid.UUID]:
        async with SessionFactory() as session:
            marker = Product(name_fa=marker_name, status="active")
            session.add(marker)
            await session.flush()  # the caller's own prior transaction work
            try:
                order = await CheckoutService().create_order_uncommitted(
                    session,
                    customer_identity_id=capacity_seed.customer_id,
                    household_id=capacity_seed.household_id,
                    address_id=capacity_seed.address_id,
                    items=[CheckoutItem(capacity_seed.offer_id, 1)],
                    idempotency_key=shared_key,
                    allowed_modes=frozenset({"full_payment"}),
                )
                outcome = f"ok:{order.id}"
            except CheckoutError as exc:
                outcome = f"conflict:{exc}"
            # The assertion that matters: committing here must succeed and
            # must not silently be a no-op for the marker row, regardless
            # of which branch above was taken.
            await session.commit()
            return outcome, marker.id

    marker_a_name = f"marker-a-{uuid.uuid4().hex}"
    marker_b_name = f"marker-b-{uuid.uuid4().hex}"
    (outcome_a, marker_a_id), (outcome_b, marker_b_id) = await asyncio.gather(
        attempt(marker_a_name), attempt(marker_b_name)
    )

    async with SessionFactory() as session:
        marker_a = await session.get(Product, marker_a_id)
        marker_b = await session.get(Product, marker_b_id)
        orders = (
            await session.scalars(
                select(Order).where(Order.checkout_idempotency_key == shared_key)
            )
        ).all()

    # Both callers' own prior work committed successfully -- neither was
    # silently discarded by the other side's idempotency-conflict handling.
    assert marker_a is not None and marker_a.name_fa == marker_a_name
    assert marker_b is not None and marker_b.name_fa == marker_b_name
    # Exactly one real order was created for the shared idempotency key,
    # regardless of which attempt's flush won the race.
    assert len(orders) == 1
    assert outcome_a.startswith("ok:") and outcome_b.startswith("ok:"), (outcome_a, outcome_b)
    assert outcome_a.split(":", 1)[1] == outcome_b.split(":", 1)[1] == str(orders[0].id)
