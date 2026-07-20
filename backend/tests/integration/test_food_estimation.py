from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from app.api.dependencies import get_current_identity
from app.common.time import utc_now
from app.db.session import SessionFactory, close_database
from app.main import create_app
from app.modules.food_estimation.models import FoodEstimate
from app.modules.households.models import Household, HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.inventory.models import InventoryUnit
from app.modules.inventory.service import InventoryError, InventoryService
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL is required",
)


@pytest.fixture(autouse=True)
async def dispose_engine_between_event_loops() -> AsyncIterator[None]:
    yield
    await close_database()


async def _seed_unit() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98919{token[:7]}", status="active"
        )
        household = Household(name=f"hh-food-est-{token}")
        session.add_all([customer, household])
        await session.flush()
        session.add(
            HouseholdMembership(household_id=household.id, identity_id=customer.id, role="owner")
        )
        unit = InventoryUnit(
            household_id=household.id,
            source="platform_order",
            state="unopened",
            label=f"unit-{token}",
            initial_quantity_grams=3000,
        )
        session.add(unit)
        await session.commit()
        return customer.id, household.id, unit.id


async def _active_estimates(unit_id: uuid.UUID) -> list[FoodEstimate]:
    async with SessionFactory() as session:
        return list(
            (
                await session.scalars(
                    select(FoodEstimate).where(
                        FoodEstimate.inventory_unit_id == unit_id,
                        FoodEstimate.status == "active",
                    )
                )
            ).all()
        )


# --- service-level: replay safety --------------------------------------


async def test_open_creates_exactly_one_active_estimate() -> None:
    _, _, unit_id = await _seed_unit()
    async with SessionFactory() as session:
        await InventoryService().open_and_estimate(
            session,
            inventory_unit_id=unit_id,
            remaining_grams=900,
            remaining_low_grams=900,
            remaining_high_grams=900,
            remaining_input_mode="grams",
            remaining_provenance={},
            feeding_context="unknown",
            daily_portion_grams=None,
        )
    assert len(await _active_estimates(unit_id)) == 1


async def test_reopening_with_identical_facts_is_idempotent() -> None:
    _, _, unit_id = await _seed_unit()

    async def _open() -> FoodEstimate:
        async with SessionFactory() as session:
            return await InventoryService().open_and_estimate(
                session,
                inventory_unit_id=unit_id,
                remaining_grams=900,
                remaining_low_grams=900,
                remaining_high_grams=900,
                remaining_input_mode="grams",
                remaining_provenance={},
                feeding_context="unknown",
                daily_portion_grams=None,
            )

    first = await _open()
    second = await _open()
    assert first.id == second.id
    assert len(await _active_estimates(unit_id)) == 1


async def test_reopening_with_different_facts_requires_correction_endpoint() -> None:
    _, _, unit_id = await _seed_unit()
    async with SessionFactory() as session:
        await InventoryService().open_and_estimate(
            session,
            inventory_unit_id=unit_id,
            remaining_grams=900,
            remaining_low_grams=900,
            remaining_high_grams=900,
            remaining_input_mode="grams",
            remaining_provenance={},
            feeding_context="unknown",
            daily_portion_grams=None,
        )
    async with SessionFactory() as session:
        with pytest.raises(InventoryError, match="unit_already_opened_use_correction_endpoint"):
            await InventoryService().open_and_estimate(
                session,
                inventory_unit_id=unit_id,
                remaining_grams=400,
                remaining_low_grams=400,
                remaining_high_grams=400,
                remaining_input_mode="grams",
                remaining_provenance={},
                feeding_context="unknown",
                daily_portion_grams=None,
            )
    assert len(await _active_estimates(unit_id)) == 1


async def test_reopening_same_grams_different_feeding_context_requires_correction() -> None:
    """Gap-closure fix (Workstream 8): the replay-safety check used to
    compare only remaining_quantity_grams/remaining_low_grams/
    remaining_high_grams/remaining_input_mode -- feeding_context and
    daily_portion_grams were never compared at all, so a request that
    changed only one of those two was wrongly treated as a safe replay
    and silently returned the stale estimate instead of being rejected."""
    _, _, unit_id = await _seed_unit()
    async with SessionFactory() as session:
        first = await InventoryService().open_and_estimate(
            session,
            inventory_unit_id=unit_id,
            remaining_grams=900,
            remaining_low_grams=900,
            remaining_high_grams=900,
            remaining_input_mode="grams",
            remaining_provenance={},
            feeding_context="unknown",
            daily_portion_grams=None,
        )
    async with SessionFactory() as session:
        with pytest.raises(InventoryError, match="unit_already_opened_use_correction_endpoint"):
            await InventoryService().open_and_estimate(
                session,
                inventory_unit_id=unit_id,
                remaining_grams=900,
                remaining_low_grams=900,
                remaining_high_grams=900,
                remaining_input_mode="grams",
                remaining_provenance={},
                feeding_context="exclusive",
                daily_portion_grams=100,
            )
    estimates = await _active_estimates(unit_id)
    assert len(estimates) == 1
    assert estimates[0].id == first.id


async def test_new_estimate_records_algorithm_version_and_request_hash() -> None:
    _, _, unit_id = await _seed_unit()
    async with SessionFactory() as session:
        estimate = await InventoryService().open_and_estimate(
            session,
            inventory_unit_id=unit_id,
            remaining_grams=900,
            remaining_low_grams=900,
            remaining_high_grams=900,
            remaining_input_mode="grams",
            remaining_provenance={},
            feeding_context="exclusive",
            daily_portion_grams=100,
        )
    assert estimate.algorithm_version == "v1"
    assert estimate.request_hash is not None and len(estimate.request_hash) == 64
    assert estimate.provenance is not None
    assert estimate.provenance["schema_version"] == 2
    assert estimate.provenance["daily_portion_grams_requested"] == 100
    assert estimate.provenance["daily_portion_grams_applied"] == 100


async def test_exhaust_retires_the_active_estimate() -> None:
    customer_id, _, unit_id = await _seed_unit()
    async with SessionFactory() as session:
        await InventoryService().open_and_estimate(
            session,
            inventory_unit_id=unit_id,
            remaining_grams=900,
            remaining_low_grams=900,
            remaining_high_grams=900,
            remaining_input_mode="grams",
            remaining_provenance={},
            feeding_context="unknown",
            daily_portion_grams=None,
        )

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/api/v1/pet-life/inventory/{unit_id}/exhaust")
    app.dependency_overrides.clear()
    assert response.status_code == 204
    assert await _active_estimates(unit_id) == []


# --- database-level: the partial unique index itself -----------------------


async def test_partial_unique_index_rejects_a_second_active_row() -> None:
    _, _, unit_id = await _seed_unit()
    async with SessionFactory() as session:
        first = FoodEstimate(
            inventory_unit_id=unit_id,
            low_days=5,
            high_days=8,
            confidence="medium",
            status="active",
            calculated_at=utc_now(),
            basis="owner_confirmed_portion",
        )
        session.add(first)
        await session.commit()

    async with SessionFactory() as session:
        second = FoodEstimate(
            inventory_unit_id=unit_id,
            low_days=3,
            high_days=4,
            confidence="medium",
            status="active",
            calculated_at=utc_now(),
            basis="owner_confirmed_portion",
        )
        session.add(second)
        with pytest.raises(IntegrityError):
            await session.commit()


# --- concurrency ---------------------------------------------------------


async def _race_open(unit_id: uuid.UUID, *, delay: float = 0.0) -> str:
    if delay:
        await asyncio.sleep(delay)
    async with SessionFactory() as session:
        try:
            await InventoryService().open_and_estimate(
                session,
                inventory_unit_id=unit_id,
                remaining_grams=900,
                remaining_low_grams=900,
                remaining_high_grams=900,
                remaining_input_mode="grams",
                remaining_provenance={},
                feeding_context="unknown",
                daily_portion_grams=None,
            )
        except InventoryError:
            return "rejected"
        return "opened"


async def test_concurrent_open_attempts_never_produce_two_active_rows() -> None:
    for _ in range(5):
        _, _, unit_id = await _seed_unit()
        results = await asyncio.gather(
            _race_open(unit_id), _race_open(unit_id, delay=0.01)
        )
        assert "opened" in results
        assert len(await _active_estimates(unit_id)) == 1
