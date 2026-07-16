from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.api.routes.pet_life import OpenInventoryBody, _remaining_facts
from app.core.config import Settings
from app.main import create_app
from app.modules.food_estimation.models import FoodEstimate
from app.modules.inventory.models import ConsumptionAssignment, InventoryUnit, ReorderSnooze
from app.modules.orders.models import Order
from app.modules.pets.models import Pet
from app.modules.today.service import build_today
from fastapi import HTTPException


def test_k9_2_routes_and_unions_are_in_checked_application_contract() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]
    schemas = schema["components"]["schemas"]
    assert "/api/v1/pet-life/inventory/{unit_id}" in paths
    assert "/api/v1/pet-life/inventory/{unit_id}/reorder-assessment" in paths
    assert "/api/v1/pet-life/inventory/{unit_id}/reorder-snooze" in paths
    today_mapping = schemas["TodayResponse"]["properties"]["food"]["discriminator"]["mapping"]
    assert set(today_mapping) == {
        "none",
        "incoming",
        "unopened",
        "unknown_estimate",
        "estimated",
        "unavailable",
    }
    assert "outcome" in schemas["ReorderAssessmentResponse"]["properties"]


class _RemainingSession:
    async def scalar(self, query: object) -> object:
        return 2000


@pytest.mark.asyncio
async def test_exact_grams_input_preserves_legacy_and_new_contracts() -> None:
    settings = Settings()
    unit = InventoryUnit(
        id=uuid4(),
        household_id=uuid4(),
        source="external_purchase",
        state="unopened",
        label="food",
    )
    legacy = await _remaining_facts(
        _RemainingSession(),
        unit,
        OpenInventoryBody(remaining_grams=2100),
        settings,
    )
    modern = await _remaining_facts(
        _RemainingSession(),
        unit,
        OpenInventoryBody(remaining={"mode": "grams", "grams": 2100}),
        settings,
    )
    assert legacy["remaining_low_grams"] == 2100
    assert modern["remaining_high_grams"] == 2100
    assert modern["remaining_provenance"]["contract_version"] == 1


@pytest.mark.asyncio
async def test_level_input_stores_honest_bounds_without_exact_grams() -> None:
    body = OpenInventoryBody(
        remaining={"mode": "level", "level": "more_than_half"},
        daily_portion_grams=85,
    )
    unit = InventoryUnit(
        id=uuid4(),
        household_id=uuid4(),
        source="external_purchase",
        state="unopened",
        label="food",
        initial_quantity_grams=2000,
    )
    facts = await _remaining_facts(_RemainingSession(), unit, body, Settings())
    assert facts["remaining_grams"] is None
    assert facts["remaining_low_grams"] == 1000
    assert facts["remaining_high_grams"] == 1500
    assert facts["remaining_input_mode"] == "level"
    assert facts["remaining_provenance"]["level"] == "more_than_half"


@pytest.mark.asyncio
async def test_level_input_fails_closed_when_nominal_quantity_is_unknown() -> None:
    body = OpenInventoryBody(remaining={"mode": "level", "level": "more_than_half"})
    unit = InventoryUnit(
        id=uuid4(),
        household_id=uuid4(),
        source="external_purchase",
        state="unopened",
        label="food",
    )
    with pytest.raises(HTTPException) as exc_info:
        await _remaining_facts(_RemainingSession(), unit, body, Settings())
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "semantic_level_nominal_quantity_required"


class _ExecuteResult:
    def __init__(self, first_result: object) -> None:
        self._first_result = first_result

    def first(self) -> object:
        return self._first_result


class _Session:
    def __init__(self, *, pet: Pet, food_row: object, scalars: list[object]) -> None:
        self._pet = pet
        self._food_row = food_row
        self._scalars = scalars

    async def get(self, model: object, item_id: object) -> object:
        return self._pet

    async def execute(self, query: object) -> _ExecuteResult:
        return _ExecuteResult(self._food_row)

    async def scalar(self, query: object) -> object:
        return self._scalars.pop(0)


@pytest.mark.asyncio
async def test_today_incoming_only_uses_planned_pet_order() -> None:
    household_id = uuid4()
    pet = Pet(id=uuid4(), household_id=household_id, name="Milo", species="cat", status="active")
    order = Order(
        id=uuid4(),
        household_id=household_id,
        customer_identity_id=uuid4(),
        status="paid",
        currency="IRR",
        merchandise_total_irr=1,
        checkout_idempotency_key="k",
        delivery_address_snapshot={},
    )
    today = await build_today(
        _Session(pet=pet, food_row=None, scalars=[order, None, None, 0, None]),
        pet_id=pet.id,
    )
    assert today["food"]["state"] == "incoming"
    assert today["food"]["order_id"] == order.id
    assert today["primary_attention"] is None


@pytest.mark.asyncio
async def test_today_unknown_share_does_not_leak_pet_remaining_days() -> None:
    household_id = uuid4()
    unit_id = uuid4()
    pet = Pet(id=uuid4(), household_id=household_id, name="Milo", species="cat", status="active")
    unit = InventoryUnit(
        id=unit_id,
        household_id=household_id,
        source="external_purchase",
        state="opened",
        label="food",
    )
    estimate = FoodEstimate(
        id=uuid4(),
        inventory_unit_id=unit_id,
        low_days=4,
        high_days=6,
        confidence="medium",
        status="active",
        calculated_at=datetime.now(UTC),
        basis="owner_confirmed_portion",
    )
    assignment = ConsumptionAssignment(
        id=uuid4(),
        inventory_unit_id=unit_id,
        pet_id=pet.id,
        share_basis_points=None,
    )
    today = await build_today(
        _Session(
            pet=pet,
            food_row=(unit, estimate, assignment),
            scalars=[None, None, None, 0, None, None],
        ),
        pet_id=pet.id,
    )
    assert today["food"]["state"] == "unknown_estimate"
    assert "remaining_low_days" not in today["food"]
    assert today["primary_attention"] == {"type": "improve_food_estimate"}


@pytest.mark.asyncio
async def test_today_reorder_snooze_breaks_only_when_policy_threshold_crosses() -> None:
    household_id = uuid4()
    unit_id = uuid4()
    pet = Pet(id=uuid4(), household_id=household_id, name="Milo", species="cat", status="active")
    unit = InventoryUnit(
        id=unit_id,
        household_id=household_id,
        source="external_purchase",
        state="opened",
        label="food",
    )
    estimate = FoodEstimate(
        id=uuid4(),
        inventory_unit_id=unit_id,
        low_days=15,
        high_days=20,
        confidence="medium",
        status="active",
        calculated_at=datetime.now(UTC),
        basis="owner_confirmed_portion",
    )
    assignment = ConsumptionAssignment(
        id=uuid4(),
        inventory_unit_id=unit_id,
        pet_id=pet.id,
        share_basis_points=None,
    )
    snooze = ReorderSnooze(
        id=uuid4(),
        inventory_unit_id=unit_id,
        household_id=household_id,
        identity_id=uuid4(),
        snoozed_from=datetime.now(UTC),
        snoozed_until=datetime.max.replace(tzinfo=UTC),
        baseline_low_days=17,
    )
    today = await build_today(
        _Session(
            pet=pet,
            food_row=(unit, estimate, assignment),
            scalars=[None, None, None, 0, None, snooze],
        ),
        pet_id=pet.id,
    )
    assert today["primary_attention"] == {"type": "improve_food_estimate"}
