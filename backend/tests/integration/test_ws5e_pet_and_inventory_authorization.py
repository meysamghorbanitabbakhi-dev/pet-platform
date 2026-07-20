from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import pytest
from app.api.dependencies import get_current_identity
from app.db.session import SessionFactory, close_database
from app.main import create_app
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


@dataclass(slots=True)
class PetAuthSeed:
    identity: AuthIdentity
    household_id: uuid.UUID
    pet_id: uuid.UUID
    other_household_id: uuid.UUID
    other_pet_id: uuid.UUID
    other_inventory_unit_id: uuid.UUID
    """Owned by other_household -- never identity's."""


@pytest.fixture()
async def pet_auth_seed() -> PetAuthSeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98922{token[:7]}", status="active"
        )
        other_identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98923{token[:7]}", status="active"
        )
        household = Household(name=f"ws5e-hh-{token}")
        other_household = Household(name=f"ws5e-other-hh-{token}")
        session.add_all([identity, other_identity, household, other_household])
        await session.flush()
        session.add_all(
            [
                HouseholdMembership(
                    household_id=household.id, identity_id=identity.id, role="owner"
                ),
                HouseholdMembership(
                    household_id=other_household.id,
                    identity_id=other_identity.id,
                    role="owner",
                ),
            ]
        )
        pet = Pet(household_id=household.id, name="Milo", species="cat", status="active")
        other_pet = Pet(
            household_id=other_household.id, name="Nilo", species="cat", status="active"
        )
        other_unit = InventoryUnit(
            household_id=other_household.id,
            source="platform_order",
            state="unopened",
            label=f"ws5e-unit-{token}",
            initial_quantity_grams=3000,
        )
        session.add_all([pet, other_pet, other_unit])
        await session.commit()
        return PetAuthSeed(
            identity=identity,
            household_id=household.id,
            pet_id=pet.id,
            other_household_id=other_household.id,
            other_pet_id=other_pet.id,
            other_inventory_unit_id=other_unit.id,
        )


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def test_pet_health_routes_are_non_enumerating_for_a_foreign_pet(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], pet_auth_seed: PetAuthSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: pet_auth_seed.identity
    other_pet_id = pet_auth_seed.other_pet_id

    profile = await client.get(f"/api/v1/pet-life/pets/{other_pet_id}/profile")
    assert profile.status_code == 404

    care_guidance = await client.get(f"/api/v1/pet-life/pets/{other_pet_id}/care-guidance")
    assert care_guidance.status_code == 404

    measurements_list = await client.get(f"/api/v1/pet-life/pets/{other_pet_id}/measurements")
    assert measurements_list.status_code == 404

    weight_trend = await client.get(f"/api/v1/pet-life/pets/{other_pet_id}/weight-trend")
    assert weight_trend.status_code == 404

    record = await client.post(
        f"/api/v1/pet-life/pets/{other_pet_id}/measurements",
        json={
            "measurement_type": "weight",
            "value": "4.5",
            "unit": "kg",
            "measured_at": datetime.now(UTC).isoformat(),
            "source": "owner_reported",
        },
    )
    assert record.status_code == 404


async def test_pet_assets_routes_are_non_enumerating_for_a_foreign_pet(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], pet_auth_seed: PetAuthSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: pet_auth_seed.identity
    other_pet_id = pet_auth_seed.other_pet_id

    assets = await client.get(f"/api/v1/pet-life/pets/{other_pet_id}/assets")
    assert assets.status_code == 404

    body_assessments = await client.get(
        f"/api/v1/pet-life/pets/{other_pet_id}/body-assessments"
    )
    assert body_assessments.status_code == 404

    upload = await client.post(
        f"/api/v1/pet-life/pets/{other_pet_id}/assets",
        headers={
            "X-Filename": "test.jpg",
            "X-Asset-Category": "other_medical",
            "X-Consent-ID": str(uuid.uuid4()),
            "Content-Type": "image/jpeg",
        },
        content=b"not-a-real-image",
    )
    assert upload.status_code == 404


async def test_inventory_routes_are_non_enumerating_for_a_foreign_household(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], pet_auth_seed: PetAuthSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: pet_auth_seed.identity
    other_unit_id = pet_auth_seed.other_inventory_unit_id

    detail = await client.get(f"/api/v1/pet-life/inventory/{other_unit_id}")
    assert detail.status_code == 404

    opened = await client.post(
        f"/api/v1/pet-life/inventory/{other_unit_id}/open",
        json={"remaining_grams": 500},
    )
    assert opened.status_code == 404

    snoozed = await client.put(
        f"/api/v1/pet-life/inventory/{other_unit_id}/reorder-snooze", json={"hours": 24}
    )
    assert snoozed.status_code == 404

    async with SessionFactory() as session:
        unit = await session.get(InventoryUnit, other_unit_id)
        assert unit is not None
        # The foreign unit must be completely untouched by the rejected
        # open attempt -- authorization failure is not just a wrong status
        # code, it must be a true no-op on someone else's data.
        assert unit.state == "unopened"
        assert unit.remaining_quantity_grams is None


async def test_diary_and_garden_routes_are_non_enumerating_for_a_foreign_pet(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], pet_auth_seed: PetAuthSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: pet_auth_seed.identity
    other_pet_id = pet_auth_seed.other_pet_id

    diary = await client.get(f"/api/v1/pet-life/pets/{other_pet_id}/diary")
    assert diary.status_code == 404

    garden = await client.get(f"/api/v1/pet-life/pets/{other_pet_id}/garden")
    assert garden.status_code == 404


async def test_household_listing_routes_are_non_enumerating_for_a_foreign_household(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], pet_auth_seed: PetAuthSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: pet_auth_seed.identity
    other_household_id = pet_auth_seed.other_household_id

    pets = await client.get(f"/api/v1/pet-life/households/{other_household_id}/pets")
    assert pets.status_code == 404

    wallet = await client.get(f"/api/v1/pet-life/households/{other_household_id}/wallet")
    assert wallet.status_code == 404

    inventory = await client.get(
        f"/api/v1/pet-life/households/{other_household_id}/inventory"
    )
    assert inventory.status_code == 404
