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
