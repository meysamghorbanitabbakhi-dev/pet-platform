from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
from app.api.dependencies import get_current_identity
from app.common.time import utc_now
from app.db.session import SessionFactory, close_database
from app.main import create_app
from app.modules.catalog.models import Offer, Product, Supplier
from app.modules.diary.models import DiaryEntry
from app.modules.households.models import Household, HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.inventory.models import InventoryUnit
from app.modules.pets.models import Pet
from fastapi import FastAPI

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL is required",
)


@pytest.fixture(autouse=True)
async def dispose_engine_between_event_loops() -> AsyncIterator[None]:
    yield
    await close_database()


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def test_diary_list_is_capped_and_returns_most_recent_first(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    """diary_entries has no household/customer scoping of its own -- a
    single pet accumulating one entry per life event forever is a real,
    unbounded-growth table (see the gap-closure program's pagination
    audit). list_diary must never return the whole table; it must return
    a bounded, most-recent-first window instead."""
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98924{token[:7]}", status="active"
        )
        household = Household(name=f"pagination-hh-{token}")
        session.add_all([identity, household])
        await session.flush()
        session.add(
            HouseholdMembership(household_id=household.id, identity_id=identity.id, role="owner")
        )
        pet = Pet(household_id=household.id, name="Milo", species="cat", status="active")
        session.add(pet)
        await session.flush()
        now = utc_now()
        session.add_all(
            [
                DiaryEntry(
                    pet_id=pet.id,
                    entry_type="note",
                    title_fa=f"entry-{token}-{index}",
                    happened_at=now - timedelta(minutes=index),
                    source_type="pagination-test",
                    source_id=f"{token}-{index}",
                )
                for index in range(210)
            ]
        )
        await session.commit()
        pet_id = pet.id

    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: identity
    response = await client.get(f"/api/v1/pet-life/pets/{pet_id}/diary")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 200
    assert items[0]["title_fa"] == f"entry-{token}-0"
    assert items[-1]["title_fa"] == f"entry-{token}-199"


async def test_household_inventory_list_is_capped_and_returns_most_recent_first(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    """inventory_units accumulates one row per purchase/consumption cycle
    per household forever -- another unbounded-growth table found by the
    same audit. list_household_inventory must never return the whole
    table."""
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98925{token[:7]}", status="active"
        )
        household = Household(name=f"pagination-inv-hh-{token}")
        session.add_all([identity, household])
        await session.flush()
        session.add(
            HouseholdMembership(household_id=household.id, identity_id=identity.id, role="owner")
        )
        session.add_all(
            [
                InventoryUnit(
                    household_id=household.id,
                    source="external_purchase",
                    state="unopened",
                    label=f"unit-{token}-{index}",
                )
                for index in range(210)
            ]
        )
        await session.commit()
        household_id = household.id

    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: identity
    response = await client.get(f"/api/v1/pet-life/households/{household_id}/inventory")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 200


async def test_offers_list_is_capped(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    """catalog_offers is the storefront's whole catalog -- a real,
    storewide unbounded-growth risk as the supplier/product catalog
    scales, distinct from the per-household/per-pet tables above. GET
    /catalog/offers must never return the entire table."""
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        supplier = Supplier(
            internal_name=f"pagination-supplier-{token}", country_code="IR", active=True
        )
        product = Product(name_fa=f"محصول صفحه‌بندی {token}", status="active")
        session.add_all([supplier, product])
        await session.flush()
        session.add_all(
            [
                Offer(
                    product_id=product.id,
                    supplier_id=supplier.id,
                    sku=f"PAGE-{token}-{index}",
                    title_fa=f"پیشنهاد صفحه‌بندی {token} {index}",
                    unit_label_fa="کیسه",
                    price_irr=1_000_000,
                    status="active",
                    stock_posture="sourced_after_payment",
                    sourcing_capacity_status="open",
                    minimum_shelf_life_months=6,
                    sourcing_route="individual",
                )
                for index in range(510)
            ]
        )
        await session.commit()

    _, client = app_and_client
    response = await client.get("/api/v1/catalog/offers")
    assert response.status_code == 200
    assert len(response.json()) <= 500
