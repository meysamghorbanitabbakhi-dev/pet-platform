from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EventDisposition = Literal["handler", "audit_only"]


@dataclass(frozen=True, slots=True)
class EventDefinition:
    event_type: str
    disposition: EventDisposition
    description: str


EVENT_REGISTRY: dict[str, EventDefinition] = {
    "order.awaiting_payment": EventDefinition(
        event_type="order.awaiting_payment",
        disposition="audit_only",
        description="Commercial order snapshot was created before payment.",
    ),
    "order.payment_verified": EventDefinition(
        event_type="order.payment_verified",
        disposition="audit_only",
        description="Payment verified and sourcing may proceed through committed state.",
    ),
    "wallet.late_delivery_credit_granted": EventDefinition(
        event_type="wallet.late_delivery_credit_granted",
        disposition="handler",
        description="Creates customer-visible wallet credit notification when policy-visible.",
    ),
    "catalog.offer_available": EventDefinition(
        event_type="catalog.offer_available",
        disposition="audit_only",
        description="Availability subscription activation notification was recorded.",
    ),
    "journey.completed": EventDefinition(
        event_type="journey.completed",
        disposition="audit_only",
        description="Journey completion created diary and Garden effects.",
    ),
    "orders.shelf_life_exception_proposed": EventDefinition(
        event_type="orders.shelf_life_exception_proposed",
        disposition="handler",
        description="Notifies the household owner a shelf-life exception needs a response.",
    ),
    "reservations.proposed": EventDefinition(
        event_type="reservations.proposed",
        disposition="handler",
        description="Notifies the household owner a reservation's reconfirmed terms need response.",
    ),
}


def event_disposition(event_type: str) -> EventDisposition | None:
    definition = EVENT_REGISTRY.get(event_type)
    return definition.disposition if definition else None
