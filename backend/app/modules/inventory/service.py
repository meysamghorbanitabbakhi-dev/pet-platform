from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.food_estimation.models import FoodEstimate
from app.modules.inventory.models import ConsumptionAssignment, InventoryUnit
from app.modules.system.idempotency import canonical_request_hash

# Bump when the low_days/high_days formula below changes materially --
# each FoodEstimate row records the version that produced it (see the
# model's own docstring), and open_and_estimate's replay-safety check
# folds this into the hash so a formula change never gets silently
# masked as "the same request, safe to replay."
_ALGORITHM_VERSION = "v1"


class InventoryError(Exception):
    pass


def _estimate_request_hash(
    *,
    remaining_grams: int | None,
    remaining_low_grams: int,
    remaining_high_grams: int,
    remaining_input_mode: str,
    feeding_context: str,
    daily_portion_grams: int | None,
) -> str:
    return canonical_request_hash(
        {
            "algorithm_version": _ALGORITHM_VERSION,
            "remaining_grams": remaining_grams,
            "remaining_low_grams": remaining_low_grams,
            "remaining_high_grams": remaining_high_grams,
            "remaining_input_mode": remaining_input_mode,
            "feeding_context": feeding_context,
            "daily_portion_grams": daily_portion_grams,
        }
    )


class InventoryService:
    async def open_and_estimate(
        self,
        session: AsyncSession,
        *,
        inventory_unit_id: UUID,
        remaining_grams: int | None,
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
        if remaining_grams is not None and remaining_grams <= 0:
            raise InventoryError("remaining quantity must be positive")
        if remaining_low_grams < 0 or remaining_high_grams < remaining_low_grams:
            raise InventoryError("remaining bounds are invalid")
        if remaining_high_grams <= 0:
            raise InventoryError("remaining quantity must be positive")

        # Hashes the request as the caller actually submitted it (the raw
        # daily_portion_grams, before the "derive it from pet assignments
        # if the caller left it unset" logic below runs) -- what matters
        # for replay-safety is whether this is the same request, not
        # whether it happens to land on the same derived number.
        request_hash = _estimate_request_hash(
            remaining_grams=remaining_grams,
            remaining_low_grams=remaining_low_grams,
            remaining_high_grams=remaining_high_grams,
            remaining_input_mode=remaining_input_mode,
            feeding_context=feeding_context,
            daily_portion_grams=daily_portion_grams,
        )
        requested_daily_portion_grams = daily_portion_grams

        existing_active = await session.scalar(
            select(FoodEstimate).where(
                FoodEstimate.inventory_unit_id == unit.id,
                FoodEstimate.status == "active",
            )
        )
        if existing_active is not None:
            # A caller reaching here with an active estimate already on
            # record means this is a raw reopen of an already-opened unit
            # (correct_estimate/exhaust_inventory always retire the active
            # row themselves before calling in). Replay-safe only for an
            # exact repeat of the same request -- anything else (including
            # a change to feeding_context or daily_portion_grams, which
            # the previous, narrower comparison here did not check at
            # all) must go through the correction endpoint, which
            # explicitly retires the old estimate first (see PostgreSQL
            # partial unique index one_active_estimate_per_unit, migration
            # 20260720_0036). A legacy row with no request_hash on record
            # (predates this check) can never match a replay and always
            # falls through to the correction-endpoint error.
            if existing_active.request_hash == request_hash:
                return existing_active
            raise InventoryError("unit_already_opened_use_correction_endpoint")

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
            low_days = remaining_low_grams // daily_portion_grams
            high_days = max(low_days, remaining_high_grams // daily_portion_grams)
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
            algorithm_version=_ALGORITHM_VERSION,
            request_hash=request_hash,
            provenance={
                "schema_version": 2,
                "remaining_input_mode": remaining_input_mode,
                "remaining_grams": remaining_grams,
                "remaining_low_grams": remaining_low_grams,
                "remaining_high_grams": remaining_high_grams,
                "feeding_context": feeding_context,
                "daily_portion_grams_requested": requested_daily_portion_grams,
                "daily_portion_grams_applied": daily_portion_grams,
                **remaining_provenance,
            },
        )
        session.add(estimate)
        await session.commit()
        return estimate
