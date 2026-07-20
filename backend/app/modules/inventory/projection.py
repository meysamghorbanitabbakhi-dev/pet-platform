from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.catalog.models import Offer
from app.modules.inventory.models import ConsumptionAssignment, InventoryUnit
from app.modules.orders.models import Order, OrderLine, OrderLinePetPlan
from app.modules.trust.models import SourcedUnitEvidence


class DeliveryProjectionError(Exception):
    pass


async def project_delivered_order(
    session: AsyncSession, *, order_id: UUID, household_id: UUID
) -> list[InventoryUnit]:
    order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None or order.status != "delivered" or order.delivered_at is None:
        raise DeliveryProjectionError("order cannot be marked delivered")
    if order.household_id != household_id:
        raise DeliveryProjectionError("order belongs to a different household")
    rows = (
        await session.execute(
            select(OrderLine, Offer, SourcedUnitEvidence)
            .join(Offer, Offer.id == OrderLine.offer_id)
            .outerjoin(
                SourcedUnitEvidence,
                SourcedUnitEvidence.order_line_id == OrderLine.id,
            )
            .where(OrderLine.order_id == order.id)
        )
    ).all()
    now = utc_now()
    units: list[InventoryUnit] = []
    for line, offer, evidence in rows:
        if line.excluded_from_delivery_at is not None:
            continue
        if evidence is None:
            raise DeliveryProjectionError(
                f"order line {line.id} has no confirmed sourced-unit evidence"
            )
        if evidence.exact_expiry_date < now.date():
            # The confirmed expiry date (set at sourcing-confirmation time,
            # or a shelf-life exception's accepted proposal) can be days
            # old by the time delivery actually happens -- a slow
            # fulfillment on a short-shelf-life exception must not ship an
            # already-expired unit just because it was valid when
            # confirmed. Blocks the whole "mark delivered" transaction so
            # the order's status never advances while this is unresolved.
            raise DeliveryProjectionError(
                f"order line {line.id} sourced-unit evidence expired on "
                f"{evidence.exact_expiry_date.isoformat()}, before delivery"
            )
        existing = await session.scalar(
            select(InventoryUnit).where(InventoryUnit.order_line_id == line.id)
        )
        if existing is not None:
            units.append(existing)
            continue
        unit = InventoryUnit(
            household_id=household_id,
            order_line_id=line.id,
            product_id=offer.product_id,
            source="platform_order",
            state="unopened",
            label=line.title_fa_snapshot,
            delivered_at=now,
            exact_expiry_date=evidence.exact_expiry_date,
            sourcing_confirmed_at=evidence.confirmed_at,
            supplier_country_snapshot=evidence.supplier_country_snapshot,
            authenticity_basis=evidence.authenticity_basis,
        )
        session.add(unit)
        await session.flush()
        planned_pet_ids = list(
            await session.scalars(
                select(OrderLinePetPlan.pet_id).where(OrderLinePetPlan.order_line_id == line.id)
            )
        )
        for pet_id in planned_pet_ids:
            session.add(ConsumptionAssignment(inventory_unit_id=unit.id, pet_id=pet_id))
        units.append(unit)
    await session.flush()
    return units
