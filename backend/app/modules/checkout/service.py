from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.catalog.models import Offer, Product, Supplier
from app.modules.households.models import HouseholdAddress
from app.modules.orders.models import Order, OrderLine
from app.modules.system.idempotency import canonical_request_hash
from app.modules.system.outbox import DomainEvent, add_outbox_event


class CheckoutError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CheckoutItem:
    offer_id: UUID
    quantity: int


_ORDINARY_CHECKOUT_MODES = frozenset({"full_payment"})


def _checkout_request_payload(
    household_id: UUID, address_id: UUID, items: list[CheckoutItem]
) -> dict[str, object]:
    return {
        "household_id": str(household_id),
        "address_id": str(address_id),
        "items": [
            {"offer_id": str(item.offer_id), "quantity": item.quantity}
            for item in sorted(items, key=lambda item: str(item.offer_id))
        ],
    }


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
        allowed_modes: frozenset[str] = _ORDINARY_CHECKOUT_MODES,
    ) -> Order:
        """Ordinary, customer-initiated checkout: constructs the order and
        commits it as the sole content of this transaction. Every route
        that lets a customer submit an arbitrary offer_id must use this
        method (its allowed_modes default), not create_order_uncommitted.
        """
        order = await self.create_order_uncommitted(
            session,
            customer_identity_id=customer_identity_id,
            household_id=household_id,
            address_id=address_id,
            items=items,
            idempotency_key=idempotency_key,
            allowed_modes=allowed_modes,
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            replay = await session.scalar(
                select(Order).where(
                    Order.customer_identity_id == customer_identity_id,
                    Order.checkout_idempotency_key == idempotency_key,
                )
            )
            request_hash = canonical_request_hash(
                _checkout_request_payload(household_id, address_id, items)
            )
            if replay is not None and replay.checkout_request_hash in (None, request_hash):
                return replay
            raise CheckoutError("idempotency key was already used for another request") from exc
        return order

    async def create_order_uncommitted(
        self,
        session: AsyncSession,
        *,
        customer_identity_id: UUID,
        household_id: UUID,
        address_id: UUID,
        items: list[CheckoutItem],
        idempotency_key: str,
        allowed_modes: frozenset[str],
    ) -> Order:
        """No-commit order construction: participates in the caller's own
        transaction rather than owning commit/rollback itself. For a
        trusted internal conversion (reserve/replenishment/concierge
        acceptance) that must persist the order, its own workflow state
        transition (approved/accepted), and any audit/outbox rows
        atomically -- if the process crashes before the caller's own
        commit, NOTHING persists, including this order, rather than
        leaving a real order behind with no corresponding workflow-state
        update to show for it. The caller is responsible for its own
        final `await session.commit()` (and should wrap it in the same
        IntegrityError-replay pattern create_order uses above if it
        wants equivalent replay safety across the whole workflow, not
        just the order in isolation) and for choosing a narrower
        allowed_modes only when it has already independently validated
        the offer through its own domain rules (e.g. concierge acceptance
        converting the concierge_only offer it just created for that
        exact request) -- never a blanket bypass. See ADR-012.
        """
        if not items or any(item.quantity <= 0 for item in items):
            raise CheckoutError("checkout requires positive quantities")
        request_hash = canonical_request_hash(
            _checkout_request_payload(household_id, address_id, items)
        )

        existing = await session.scalar(
            select(Order).where(
                Order.customer_identity_id == customer_identity_id,
                Order.checkout_idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.checkout_request_hash not in (None, request_hash):
                raise CheckoutError("idempotency key was already used for another request")
            return existing

        address = await session.get(HouseholdAddress, address_id)
        if address is None or address.household_id != household_id or not address.active:
            raise CheckoutError("delivery address is unavailable")

        offer_ids = {item.offer_id for item in items}
        rows = (
            await session.execute(
                select(Offer, Product, Supplier)
                .join(Product, Product.id == Offer.product_id)
                .join(Supplier, Supplier.id == Offer.supplier_id)
                .where(Offer.id.in_(offer_ids))
                .with_for_update(of=Offer)
            )
        ).all()
        offers = {offer.id: (offer, product, supplier) for offer, product, supplier in rows}
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
            checkout_request_hash=request_hash,
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
        # A concurrent call with the same idempotency_key can race past the
        # `existing is None` check above (neither has committed yet) and
        # both attempt this insert; the loser hits the unique constraint on
        # flush. That failure is caught inside a SAVEPOINT (begin_nested),
        # not via session.rollback() -- this function participates in the
        # caller's own transaction (see the docstring above) and does not
        # own it, so a plain rollback here would discard anything the
        # caller already did earlier in that same transaction (e.g.
        # concierge's freshly-created Product/Offer, replenishment's
        # already-mutated reservation), not just this insert attempt. A
        # savepoint's rollback is scoped to only the work done since it was
        # opened.
        try:
            async with session.begin_nested():
                session.add(order)
                await session.flush()
        except IntegrityError as exc:
            replay = await session.scalar(
                select(Order).where(
                    Order.customer_identity_id == customer_identity_id,
                    Order.checkout_idempotency_key == idempotency_key,
                )
            )
            if replay is not None and replay.checkout_request_hash in (None, request_hash):
                return replay
            raise CheckoutError("idempotency key was already used for another request") from exc
        for item in items:
            offer, product, supplier = offers[item.offer_id]
            # Ordinary checkout (the default allowed_modes) is the
            # full_payment path only. 'reserve' offers must go through
            # app.modules.reservations (operator price/availability
            # reconfirmation first); 'concierge_only' offers are bound to
            # one specific customer/request and are only ever passed here
            # by app.modules.concierge's own trusted accept flow (via a
            # narrower allowed_modes). Both modes reach
            # status='active'/sourcing_capacity_status='open' just like an
            # ordinary offer, so without this check any customer who learns
            # the offer_id (a leaked link, a shared concierge offer id,
            # simple enumeration) could buy it here, bypassing the reserve
            # reconfirmation workflow or another household's concierge
            # verification and pricing entirely.
            if offer.mode not in allowed_modes:
                raise CheckoutError(f"offer {offer.id} is not eligible for this checkout path")
            if product.status != "active" or not supplier.active:
                raise CheckoutError(f"offer {offer.id} is unavailable")
            if offer.status != "active" or offer.stock_posture != "sourced_after_payment":
                raise CheckoutError(f"offer {offer.id} is unavailable")
            if offer.sourcing_capacity_status != "open":
                raise CheckoutError(f"offer {offer.id} sourcing capacity is paused")
            if offer.available_from is not None and now < offer.available_from:
                raise CheckoutError(f"offer {offer.id} is not available yet")
            if offer.available_until is not None and now >= offer.available_until:
                raise CheckoutError(f"offer {offer.id} availability ended")
            # Checkout preflight for the aggregated-sourcing invariant: an
            # offer left on the aggregated route with no
            # default_batch_threshold_quantity configured cannot actually
            # open a purchase batch (app.modules.purchasing.service raises
            # PurchasingError the moment payment verification tries to
            # allocate into one). Rejecting it here, before the order or
            # any payment exists, means a misconfigured offer fails
            # checkout with a clear, actionable error instead of the
            # customer discovering it only after their payment is
            # verified.
            if (
                offer.sourcing_route == "aggregated"
                and offer.default_batch_threshold_quantity is None
            ):
                raise CheckoutError(
                    f"offer {offer.id} is on the aggregated sourcing route with no "
                    "default_batch_threshold_quantity configured"
                )
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
        # No commit here -- the caller owns the transaction. flush so the
        # order/lines are visible (with real ids/FKs) to whatever the
        # caller does next in the same transaction, without finalizing it.
        await session.flush()
        return order
