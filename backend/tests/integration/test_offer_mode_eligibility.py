from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass

import httpx
import pytest
from app.api.dependencies import get_current_identity
from app.db.session import SessionFactory, close_database
from app.main import create_app
from app.modules.catalog.availability import notify_available_subscribers
from app.modules.catalog.models import (
    CatalogAvailabilitySubscription,
    Offer,
    Product,
    Supplier,
)
from app.modules.households.models import Household, HouseholdAddress, HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.inventory.models import InventoryUnit
from app.modules.notifications.models import Notification
from app.modules.replenishment.reservations import _find_available_offer
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
    """Mirrors test_concierge_offers.py's identically-named fixture: rows
    this module seeds directly with mode='concierge_only' would otherwise
    permanently block any later test that downgrades the schema past
    20260720_0035 in this shared database (that migration's downgrade
    correctly re-narrows the mode CHECK constraint, and Postgres validates
    it against existing rows) -- neutralize the value once this module's
    tests finish rather than deleting rows."""
    yield

    async def _cleanup() -> None:
        async with SessionFactory() as session:
            await session.execute(
                update(Offer).where(Offer.mode == "concierge_only").values(mode="full_payment")
            )
            await session.commit()
        await close_database()

    asyncio.run(_cleanup())


@dataclass(slots=True)
class ModeSeed:
    identity: AuthIdentity
    household_id: uuid.UUID
    address_id: uuid.UUID
    product_id: uuid.UUID
    full_payment_offer_id: uuid.UUID
    reserve_offer_id: uuid.UUID
    concierge_only_offer_id: uuid.UUID
    inventory_unit_id: uuid.UUID
    sku_token: str


@pytest.fixture()
async def mode_seed() -> ModeSeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98927{token[:7]}", status="active"
        )
        supplier = Supplier(internal_name=f"mode-supplier-{token}", country_code="IR", active=True)
        product = Product(name_fa=f"mode-product-{token}", status="active")
        household = Household(name=f"mode-hh-{token}")
        session.add_all([identity, supplier, product, household])
        await session.flush()
        session.add(
            HouseholdMembership(household_id=household.id, identity_id=identity.id, role="owner")
        )
        address = HouseholdAddress(
            household_id=household.id,
            label="خانه",
            recipient_name="Test User",
            recipient_mobile_e164=identity.mobile_e164,
            province="Tehran",
            city="Tehran",
            address_line="mode test address",
            postal_code=None,
            active=True,
        )
        common = dict(
            product_id=product.id,
            supplier_id=supplier.id,
            unit_label_fa="کیسه",
            price_irr=1_000_000,
            status="active",
            stock_posture="sourced_after_payment",
            sourcing_capacity_status="open",
            sourcing_route="individual",
            minimum_shelf_life_months=6,
        )
        full_payment_offer = Offer(
            sku=f"MODE-FP-{token}", title_fa="پرداخت کامل", mode="full_payment", **common
        )
        reserve_offer = Offer(sku=f"MODE-RSV-{token}", title_fa="رزرو", mode="reserve", **common)
        concierge_offer = Offer(
            sku=f"MODE-CNC-{token}", title_fa="کنسیرژ", mode="concierge_only", **common
        )
        session.add_all([address, full_payment_offer, reserve_offer, concierge_offer])
        await session.flush()
        unit = InventoryUnit(
            household_id=household.id,
            product_id=product.id,
            source="platform_order",
            state="opened",
            label=f"mode-unit-{token}",
            initial_quantity_grams=3000,
        )
        session.add(unit)
        await session.commit()
        return ModeSeed(
            identity=identity,
            household_id=household.id,
            address_id=address.id,
            product_id=product.id,
            full_payment_offer_id=full_payment_offer.id,
            reserve_offer_id=reserve_offer.id,
            concierge_only_offer_id=concierge_offer.id,
            inventory_unit_id=unit.id,
            sku_token=token,
        )


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def test_ordinary_checkout_rejects_reserve_and_concierge_only_offers(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], mode_seed: ModeSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: mode_seed.identity

    for label, offer_id in (
        ("reserve", mode_seed.reserve_offer_id),
        ("concierge_only", mode_seed.concierge_only_offer_id),
    ):
        response = await client.post(
            "/api/v1/checkout/orders",
            json={
                "household_id": str(mode_seed.household_id),
                "address_id": str(mode_seed.address_id),
                "items": [{"offer_id": str(offer_id), "quantity": 1}],
            },
            headers={"Idempotency-Key": f"mode-checkout-{label}-{uuid.uuid4().hex}"},
        )
        assert response.status_code == 409, label

    # A full_payment offer in the same request shape succeeds, proving the
    # rejection above is mode-specific, not a broken checkout path.
    ok = await client.post(
        "/api/v1/checkout/orders",
        json={
            "household_id": str(mode_seed.household_id),
            "address_id": str(mode_seed.address_id),
            "items": [{"offer_id": str(mode_seed.full_payment_offer_id), "quantity": 1}],
        },
        headers={"Idempotency-Key": f"mode-checkout-ok-{uuid.uuid4().hex}"},
    )
    assert ok.status_code == 201


async def test_mixed_cart_with_one_ineligible_offer_creates_no_order(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], mode_seed: ModeSeed
) -> None:
    """A cart combining an eligible and an ineligible offer must reject the
    whole checkout, not silently drop the ineligible line and charge for
    the rest."""
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: mode_seed.identity

    response = await client.post(
        "/api/v1/checkout/orders",
        json={
            "household_id": str(mode_seed.household_id),
            "address_id": str(mode_seed.address_id),
            "items": [
                {"offer_id": str(mode_seed.full_payment_offer_id), "quantity": 1},
                {"offer_id": str(mode_seed.concierge_only_offer_id), "quantity": 1},
            ],
        },
        headers={"Idempotency-Key": f"mode-checkout-mixed-{uuid.uuid4().hex}"},
    )
    assert response.status_code == 409

    listed = await client.get("/api/v1/orders")
    assert listed.status_code == 200
    assert listed.json()["page"]["total"] == 0


async def test_offer_detail_excludes_concierge_only_but_allows_reserve(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], mode_seed: ModeSeed
) -> None:
    """Direct-ID access to a concierge_only offer must be indistinguishable
    from a nonexistent id (no ownership context exists on this public,
    unauthenticated route to check against). A reserve offer's detail page
    is still publicly viewable -- only its conversion is gated."""
    app, client = app_and_client

    concierge_detail = await client.get(
        f"/api/v1/catalog/offers/{mode_seed.concierge_only_offer_id}"
    )
    nonexistent_detail = await client.get(f"/api/v1/catalog/offers/{uuid.uuid4()}")
    assert concierge_detail.status_code == nonexistent_detail.status_code == 404

    reserve_detail = await client.get(f"/api/v1/catalog/offers/{mode_seed.reserve_offer_id}")
    assert reserve_detail.status_code == 200


async def test_offer_list_and_search_exclude_reserve_and_concierge_only(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], mode_seed: ModeSeed
) -> None:
    """Uses /catalog/offers/search (scoped to this fixture's own unique SKU
    token) rather than the plain /catalog/offers list: that endpoint is
    intentionally capped (a gap-closure-program pagination fix -- see
    test_pagination_caps.py) and orders results alphabetically by title,
    so on a long-lived shared database with tens of thousands of
    accumulated offers from repeated test runs, this fixture's own offer
    is not guaranteed to fall within the first page by title alone. The
    mode-based exclusion this test actually verifies is identical on both
    endpoints (orderable_offer_filters), so search proves the same thing
    deterministically."""
    app, client = app_and_client

    listed = await client.get("/api/v1/catalog/offers/search", params={"q": mode_seed.sku_token})
    assert listed.status_code == 200
    listed_ids = {item["id"] for item in listed.json()["items"]}
    assert str(mode_seed.full_payment_offer_id) in listed_ids
    assert str(mode_seed.reserve_offer_id) not in listed_ids
    assert str(mode_seed.concierge_only_offer_id) not in listed_ids


async def test_replenishment_offer_selection_never_returns_ineligible_modes(
    mode_seed: ModeSeed,
) -> None:
    async with SessionFactory() as session:
        selected = await _find_available_offer(session, product_id=mode_seed.product_id)
    assert selected is not None
    assert selected.id == mode_seed.full_payment_offer_id
    assert selected.mode == "full_payment"


async def test_reorder_options_exclude_reserve_and_concierge_only(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], mode_seed: ModeSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: mode_seed.identity

    response = await client.post(
        f"/api/v1/pet-life/inventory/{mode_seed.inventory_unit_id}/reorder-assessment"
    )
    assert response.status_code == 200
    body = response.json()
    option_ids = {option["offer_id"] for option in body["options"]}
    assert str(mode_seed.full_payment_offer_id) in option_ids
    assert str(mode_seed.reserve_offer_id) not in option_ids
    assert str(mode_seed.concierge_only_offer_id) not in option_ids


# --- availability subscriptions: the same exclusions must apply here too ----
# (app.modules.catalog.eligibility) -- a hidden offer must not become
# discoverable, or trigger a real notification the instant it activates,
# through this alternate endpoint.


async def test_subscribe_rejects_a_concierge_only_offer(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], mode_seed: ModeSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: mode_seed.identity

    response = await client.post(
        f"/api/v1/catalog/offers/{mode_seed.concierge_only_offer_id}/availability-subscriptions"
    )
    assert response.status_code == 404


async def test_subscribe_rejects_a_reserve_offer_when_reserve_now_is_disabled(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], mode_seed: ModeSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: mode_seed.identity

    response = await client.post(
        f"/api/v1/catalog/offers/{mode_seed.reserve_offer_id}/availability-subscriptions"
    )
    assert response.status_code == 404


async def test_subscribe_succeeds_for_a_capacity_paused_full_payment_offer(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], mode_seed: ModeSeed
) -> None:
    """A subscription exists specifically to wait out transient
    unavailability (capacity paused, outside sale window) -- unlike
    concierge_only/disabled-reserve, this must still succeed."""
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: mode_seed.identity
    async with SessionFactory() as session:
        offer = await session.get(Offer, mode_seed.full_payment_offer_id)
        assert offer is not None
        offer.sourcing_capacity_status = "paused"
        await session.commit()

    response = await client.post(
        f"/api/v1/catalog/offers/{mode_seed.full_payment_offer_id}/availability-subscriptions"
    )
    assert response.status_code == 200


async def test_offer_detail_reflects_capacity_paused_as_temporarily_unavailable(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], mode_seed: ModeSeed
) -> None:
    """Before this fix, offer_detail only reflected offer.status ==
    'unavailable' or stock_posture == 'unavailable' in its `availability`
    field -- a capacity-paused or outside-sale-window offer rendered as
    fully "available" with no indication it cannot actually be bought."""
    app, client = app_and_client
    async with SessionFactory() as session:
        offer = await session.get(Offer, mode_seed.full_payment_offer_id)
        assert offer is not None
        offer.sourcing_capacity_status = "paused"
        await session.commit()

    response = await client.get(f"/api/v1/catalog/offers/{mode_seed.full_payment_offer_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["availability"] == "temporarily_unavailable"
    assert body["availability_reason_key"] == "temporarily_unavailable"


async def test_notify_available_subscribers_skips_concierge_only_offers(
    mode_seed: ModeSeed,
) -> None:
    """Even a pre-existing subscription row against a concierge_only
    offer (which subscribe_offer_availability itself now rejects, but a
    row could already exist from before that fix, or from direct data
    entry) must never trigger a real "it's available" notification --
    that would leak the offer's activation to someone with no ownership
    standing over it."""
    async with SessionFactory() as session:
        offer = await session.get(Offer, mode_seed.concierge_only_offer_id)
        assert offer is not None
        subscription = CatalogAvailabilitySubscription(
            identity_id=mode_seed.identity.id,
            household_id=mode_seed.household_id,
            offer_id=offer.id,
            status="active",
            activation_cycle=0,
        )
        session.add(subscription)
        await session.commit()
        sent = await notify_available_subscribers(session, offer)
        await session.commit()
        subscription_id = subscription.id

    assert sent == 0
    async with SessionFactory() as session:
        refreshed = await session.get(CatalogAvailabilitySubscription, subscription_id)
        assert refreshed is not None and refreshed.status == "active"
        notified = await session.scalar(
            select(Notification).where(
                Notification.event_key == "catalog.offer_available",
                Notification.recipient_identity_id == mode_seed.identity.id,
            )
        )
        assert notified is None
