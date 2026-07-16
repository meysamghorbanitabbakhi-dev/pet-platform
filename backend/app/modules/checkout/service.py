from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.catalog.models import Offer, Supplier
from app.modules.households.models import HouseholdAddress
from app.modules.orders.models import Order, OrderLine
from app.modules.system.outbox import DomainEvent, add_outbox_event


class CheckoutError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CheckoutItem:
    offer_id: UUID
    quantity: int


class CheckoutService:
    async def create_order(
        self,
        session: AsyncSession,
        *,
        customer_identity_id: UUID,
        household_id: UUID,
        address_id: UUID,
        items: list[CheckoutItem],
        idempotency_key: str,
    ) -> Order:
        if not items or any(item.quantity <= 0 for item in items):
            raise CheckoutError("checkout requires positive quantities")

        existing = await session.scalar(
            select(Order).where(
                Order.customer_identity_id == customer_identity_id,
                Order.checkout_idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing

        address = await session.get(HouseholdAddress, address_id)
        if address is None or address.household_id != household_id or not address.active:
            raise CheckoutError("delivery address is unavailable")

        offer_ids = {item.offer_id for item in items}
        rows = (
            await session.execute(
                select(Offer, Supplier)
                .join(Supplier, Supplier.id == Offer.supplier_id)
                .where(Offer.id.in_(offer_ids))
                .with_for_update(of=Offer)
            )
        ).all()
        offers = {offer.id: (offer, supplier) for offer, supplier in rows}
        if len(offers) != len(offer_ids):
            raise CheckoutError("one or more offers do not exist")

        total = 0
        now = utc_now()
        order = Order(
            customer_identity_id=customer_identity_id,
            household_id=household_id,
            status="awaiting_payment",
            currency="IRR",
            merchandise_total_irr=1,
            checkout_idempotency_key=idempotency_key,
            delivery_address_snapshot={
                "address_id": str(address.id),
                "label": address.label,
                "recipient_name": address.recipient_name,
                "recipient_mobile_e164": address.recipient_mobile_e164,
                "province": address.province,
                "city": address.city,
                "address_line": address.address_line,
                "postal_code": address.postal_code,
            },
        )
        session.add(order)
        await session.flush()
        for item in items:
            offer, supplier = offers[item.offer_id]
            if offer.status != "active" or offer.stock_posture != "sourced_after_payment":
                raise CheckoutError(f"offer {offer.id} is unavailable")
            if offer.sourcing_capacity_status != "open":
                raise CheckoutError(f"offer {offer.id} sourcing capacity is paused")
            if offer.available_from is not None and now < offer.available_from:
                raise CheckoutError(f"offer {offer.id} is not available yet")
            if offer.available_until is not None and now >= offer.available_until:
                raise CheckoutError(f"offer {offer.id} availability ended")
            if offer.max_pending_quantity is not None:
                pending = await session.scalar(
                    select(func.coalesce(func.sum(OrderLine.quantity), 0))
                    .join(Order, Order.id == OrderLine.order_id)
                    .where(
                        OrderLine.offer_id == offer.id,
                        Order.status.in_(("awaiting_payment", "paid", "sourcing")),
                    )
                )
                if int(pending or 0) + item.quantity > offer.max_pending_quantity:
                    raise CheckoutError(f"offer {offer.id} sourcing capacity is exhausted")
            line_total = offer.price_irr * item.quantity
            total += line_total
            session.add(
                OrderLine(
                    order_id=order.id,
                    offer_id=offer.id,
                    sku_snapshot=offer.sku,
                    title_fa_snapshot=offer.title_fa,
                    unit_label_fa_snapshot=offer.unit_label_fa,
                    supplier_country_snapshot=supplier.country_code,
                    quantity=item.quantity,
                    unit_price_irr=offer.price_irr,
                    line_total_irr=line_total,
                    created_at=now,
                )
            )
        order.merchandise_total_irr = total
        add_outbox_event(
            session,
            DomainEvent(
                event_type="order.awaiting_payment",
                aggregate_type="order",
                aggregate_id=str(order.id),
                payload={"order_id": str(order.id), "amount_irr": total, "currency": "IRR"},
            ),
        )
        await session.commit()
        return order
