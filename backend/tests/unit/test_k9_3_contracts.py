from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.api.routes.customer_requests import _customer_request_response
from app.api.routes.pet_life import (
    _completion_requirements_met,
    _valid_check_in,
)
from app.main import create_app
from app.modules.catalog.availability import notify_available_subscribers
from app.modules.catalog.models import CatalogAvailabilitySubscription, Offer
from app.modules.notifications.models import Notification
from app.modules.support.models import CustomerRequest


def test_k9_3_routes_are_in_checked_application_contract() -> None:
    paths = create_app().openapi()["paths"]
    assert "/api/v1/catalog/offers/{offer_id}/availability-subscriptions" in paths
    assert "/api/v1/me/availability-subscriptions" in paths
    assert "/api/v1/customer-requests" in paths
    assert "/api/v1/operator/customer-requests" in paths
    assert "/api/v1/orders/{order_id}/delay-acknowledgements" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/journey-offers" in paths
    assert "/api/v1/pet-life/journey-definitions/{definition_id}" in paths
    assert "/api/v1/pet-life/journeys/{journey_id}" in paths
    assert "/api/v1/pet-life/journeys/{journey_id}/check-ins" in paths
    assert "/api/v1/pet-life/pets/{pet_id}/diary/{entry_id}" in paths
    assert "/api/v1/pet-life/garden/{reward_id}/placement" in paths


def test_customer_request_contract_makes_no_operational_promises() -> None:
    item = CustomerRequest(
        id=uuid4(),
        identity_id=uuid4(),
        household_id=uuid4(),
        request_type="concierge_sourcing",
        message_fa="لطفا بررسی کنید",
        contact_preference="in_app",
        status="submitted",
        idempotency_key="idem",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    response = _customer_request_response(item)
    assert response.promises == {
        "availability": False,
        "refund": False,
        "replacement": False,
        "response_time": False,
        "sourcing_success": False,
    }


def test_journey_check_in_validation_and_completion_requirements() -> None:
    content = {
        "steps": [
            {"key": "water", "allowed_answers": ["done"]},
            {"key": "walk", "allowed_answers": ["short", "long"]},
        ],
        "completion_requires": ["water", "walk"],
    }
    assert _valid_check_in(content, "water", "done")
    assert not _valid_check_in(content, "water", "diagnosis")
    assert not _completion_requirements_met(content, {"water"})
    assert _completion_requirements_met(content, {"water", "walk"})


class _Scalars:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _Result:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _AvailabilitySession:
    def __init__(self, subscription: CatalogAvailabilitySubscription) -> None:
        self.subscription = subscription
        self.added: list[object] = []
        self._notification_checks = 0

    async def scalars(self, query: object) -> _Scalars:
        return _Scalars([self.subscription])

    async def scalar(self, query: object) -> object | None:
        self._notification_checks += 1
        if self._notification_checks <= 2:
            return None
        return Notification(
            recipient_identity_id=self.subscription.identity_id,
            event_key="catalog.offer_available",
            source_id=f"{self.subscription.id}:0",
            channel="in_app",
            payload={},
        )

    def add(self, item: object) -> None:
        self.added.append(item)


@pytest.mark.asyncio
async def test_availability_notification_is_once_per_activation_cycle() -> None:
    offer = Offer(
        id=uuid4(),
        product_id=uuid4(),
        supplier_id=uuid4(),
        sku="sku",
        title_fa="غذا",
        unit_label_fa="کیسه",
        price_irr=100,
        status="active",
        stock_posture="sourced_after_payment",
        sourcing_capacity_status="open",
        minimum_shelf_life_months=6,
    )
    subscription = CatalogAvailabilitySubscription(
        id=uuid4(),
        identity_id=uuid4(),
        offer_id=offer.id,
        status="active",
        activation_cycle=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session = _AvailabilitySession(subscription)
    assert await notify_available_subscribers(session, offer) == 1
    assert subscription.status == "notified"
    assert [type(item).__name__ for item in session.added].count("Notification") == 2
