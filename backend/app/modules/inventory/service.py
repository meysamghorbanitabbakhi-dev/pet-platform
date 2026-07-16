from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.food_estimation.models import FoodEstimate
from app.modules.inventory.models import ConsumptionAssignment, InventoryUnit


class InventoryError(Exception):
    pass


class InventoryService:
    async def open_and_estimate(
        self,
        session: AsyncSession,
        *,
        inventory_unit_id: UUID,
        remaining_grams: int,
        remaining_low_grams: int,
        remaining_high_grams: int,
        remaining_input_mode: str,
        remaining_provenance: dict[str, object],
        feeding_context: str,
        daily_portion_grams: int | None,
    ) -> FoodEstimate:
        unit = await session.scalar(
            select(InventoryUnit).where(InventoryUnit.id == inventory_unit_id).with_for_update()
        )
        if unit is None or unit.state not in ("unopened", "opened"):
            raise InventoryError("inventory unit cannot be opened")
        if remaining_grams <= 0:
            raise InventoryError("remaining quantity must be positive")
        unit.state = "opened"
        unit.opened_at = unit.opened_at or utc_now()
        unit.remaining_quantity_grams = remaining_grams
        unit.remaining_low_grams = remaining_low_grams
        unit.remaining_high_grams = remaining_high_grams
        unit.remaining_input_mode = remaining_input_mode
        unit.remaining_provenance = remaining_provenance

        if daily_portion_grams is not None and daily_portion_grams <= 0:
            raise InventoryError("daily portion must be positive")
        if feeding_context != "exclusive":
            daily_portion_grams = None
        if daily_portion_grams is None and feeding_context == "exclusive":
            assignments = list(
                (
                    await session.scalars(
                        select(ConsumptionAssignment).where(
                            ConsumptionAssignment.inventory_unit_id == unit.id,
                            ConsumptionAssignment.daily_portion_grams.is_not(None),
                        )
                    )
                ).all()
            )
            known_total = sum(item.daily_portion_grams or 0 for item in assignments)
            daily_portion_grams = known_total or None

        if daily_portion_grams is None:
            low_days, high_days, confidence, basis = None, None, "low", "unknown_portion"
        else:
            central = max(1, remaining_grams // daily_portion_grams)
            low_days = max(0, int(central * 0.8))
            high_days = max(low_days, int(central * 1.2))
            confidence = "medium"
            basis = "owner_confirmed_portion"
        estimate = FoodEstimate(
            inventory_unit_id=unit.id,
            low_days=low_days,
            high_days=high_days,
            confidence=confidence,
            status="active",
            calculated_at=utc_now(),
            basis=basis,
            scope="household",
            last_confirmed_at=unit.opened_at,
            provenance={
                "remaining_input_mode": remaining_input_mode,
                "remaining_low_grams": remaining_low_grams,
                "remaining_high_grams": remaining_high_grams,
                "feeding_context": feeding_context,
                **remaining_provenance,
            },
        )
        session.add(estimate)
        await session.commit()
        return estimate
