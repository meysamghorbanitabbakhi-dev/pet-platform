from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.food_estimation.models import FoodEstimate
from app.modules.garden.models import GardenReward
from app.modules.inventory.models import ConsumptionAssignment, InventoryUnit, ReorderSnooze
from app.modules.journeys.models import PetJourney
from app.modules.orders.fulfillment import FulfillmentEvent
from app.modules.orders.models import Order, OrderLine, OrderLinePetPlan
from app.modules.pet_knowledge.guidance import today_guidance
from app.modules.pets.models import Pet


async def build_today(session: AsyncSession, *, pet_id: UUID) -> dict[str, Any]:
    pet = await session.get(Pet, pet_id)
    if pet is None:
        raise ValueError("pet not found")
    now = utc_now()
    food_row = (
        await session.execute(
            select(InventoryUnit, FoodEstimate, ConsumptionAssignment)
            .join(
                ConsumptionAssignment,
                ConsumptionAssignment.inventory_unit_id == InventoryUnit.id,
            )
            .outerjoin(
                FoodEstimate,
                (FoodEstimate.inventory_unit_id == InventoryUnit.id)
                & (FoodEstimate.status == "active"),
            )
            .where(
                ConsumptionAssignment.pet_id == pet.id,
                InventoryUnit.state.in_(("unopened", "opened")),
            )
            .order_by(InventoryUnit.opened_at.desc().nullslast(), InventoryUnit.created_at)
            .limit(1)
        )
    ).first()
    planned_order = await session.scalar(
        select(Order)
        .join(OrderLine, OrderLine.order_id == Order.id)
        .join(OrderLinePetPlan, OrderLinePetPlan.order_line_id == OrderLine.id)
        .where(
            OrderLinePetPlan.pet_id == pet.id,
            Order.status.in_(("paid", "sourcing", "in_transit")),
        )
        .order_by(Order.created_at, Order.id)
        .limit(1)
    )
    failed_planned_order = await session.scalar(
        select(Order)
        .join(OrderLine, OrderLine.order_id == Order.id)
        .join(OrderLinePetPlan, OrderLinePetPlan.order_line_id == OrderLine.id)
        .where(OrderLinePetPlan.pet_id == pet.id, Order.status == "failed")
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(1)
    )
    journey = await session.scalar(
        select(PetJourney)
        .where(PetJourney.pet_id == pet.id, PetJourney.status.in_(("active", "paused")))
        .order_by(PetJourney.started_at.desc())
        .limit(1)
    )
    garden_count = await session.scalar(
        select(func.count()).select_from(GardenReward).where(GardenReward.pet_id == pet.id)
    )
    order = await session.scalar(
        select(Order)
        .where(
            Order.household_id == pet.household_id,
            Order.status.in_(("paid", "sourcing", "in_transit", "failed")),
        )
        .order_by(Order.created_at.desc())
        .limit(1)
    )
    order_attention: dict[str, Any] | None = None
    if order is not None:
        if order.status == "failed":
            order_attention = {"type": "sourcing_failed", "order_id": order.id}
        elif order.delivery_commitment_at is not None and order.delivery_commitment_at < now:
            order_attention = {"type": "delivery_overdue", "order_id": order.id}
        elif order.status == "in_transit":
            latest_event = await session.scalar(
                select(FulfillmentEvent)
                .where(FulfillmentEvent.order_id == order.id)
                .order_by(FulfillmentEvent.occurred_at.desc())
                .limit(1)
            )
            if latest_event is not None and latest_event.event_type == "delayed":
                order_attention = {"type": "delivery_delayed", "order_id": order.id}
    try:
        care_guidance = await today_guidance(session, pet=pet)
    except Exception:
        care_guidance = {}
    food: dict[str, Any]
    next_action: str | None
    if food_row is None:
        if planned_order is not None:
            food = {
                "state": "incoming",
                "order_id": planned_order.id,
                "label": "planned_delivery",
            }
        elif failed_planned_order is not None:
            food = {"state": "unavailable", "reason_key": "planned_order_failed"}
        else:
            food = {"state": "none"}
        next_action = None
    else:
        unit, estimate, assignment = food_row
        active_snooze = await session.scalar(
            select(ReorderSnooze)
            .where(
                ReorderSnooze.inventory_unit_id == unit.id,
                ReorderSnooze.household_id == pet.household_id,
                ReorderSnooze.snoozed_until > now,
            )
            .order_by(ReorderSnooze.snoozed_until.desc())
            .limit(1)
        )
        if unit.state == "unopened":
            food = {"state": "unopened", "inventory_unit_id": unit.id, "label": unit.label}
            next_action = "confirm_opening"
        elif assignment.share_basis_points is None:
            food = {
                "state": "unknown_estimate",
                "inventory_unit_id": unit.id,
                "label": unit.label,
            }
            next_action = None if active_snooze is not None else "improve_food_estimate"
        elif estimate is None or estimate.low_days is None:
            food = {
                "state": "unknown_estimate",
                "inventory_unit_id": unit.id,
                "label": unit.label,
            }
            next_action = None if active_snooze is not None else "improve_food_estimate"
        else:
            food = {
                "state": "estimated",
                "inventory_unit_id": unit.id,
                "label": unit.label,
                "remaining_low_days": estimate.low_days,
                "remaining_high_days": estimate.high_days,
                "confidence": estimate.confidence,
            }
            next_action = None
    return {
        "pet": {"id": pet.id, "name": pet.name, "species": pet.species},
        "household_id": pet.household_id,
        "generated_at": now,
        "food": food,
        "next_action": next_action,
        "primary_attention": (
            order_attention
            or ({"type": next_action} if next_action is not None else None)
            or (
                {"type": "active_journey", "journey_id": journey.id}
                if journey is not None
                else None
            )
        ),
        "active_journey": (
            {"id": journey.id, "status": journey.status} if journey is not None else None
        ),
        "garden": {"object_count": garden_count or 0},
        "care_guidance": care_guidance,
    }
