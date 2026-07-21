from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass

import httpx
import pytest
from app.api.dependencies import get_current_identity
from app.core.config import get_settings
from app.db.session import SessionFactory, close_database
from app.integrations.payment.port import (
    PaymentInitiation,
    PaymentInquiry,
    PaymentRequest,
    PaymentReversal,
    PaymentVerification,
)
from app.main import create_app
from app.modules.catalog.models import Offer, Product, Supplier
from app.modules.households.models import Household, HouseholdAddress, HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.orders.models import Order
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


class FakePaymentGateway:
    async def initiate(self, request: PaymentRequest) -> PaymentInitiation:
        return PaymentInitiation(
            provider_reference=f"fake-{request.order_id}",
            redirect_url=f"https://payments.test/{request.order_id}",
        )

    async def verify(self, *, provider_reference: str, amount_irr: int) -> PaymentVerification:
        return PaymentVerification(
            state="verified",
            provider_reference=provider_reference,
            provider_transaction_id=f"txn-{provider_reference}",
            masked_card="****1111",
            card_hash="hash",
            fee_irr=0,
        )

    async def inquiry(self, *, provider_reference: str) -> PaymentInquiry:
        return PaymentInquiry(state="verified", provider_reference=provider_reference)

    async def reverse(self, *, provider_reference: str) -> PaymentReversal:
        return PaymentReversal(reversed=True, provider_reference=provider_reference)

    async def aclose(self) -> None:
        return None


@pytest.fixture()
def reserve_now_enabled() -> Iterator[None]:
    settings = get_settings()
    settings.reserve_now_enabled = True
    try:
        yield
    finally:
        settings.reserve_now_enabled = False


@dataclass(slots=True)
class AuthSeed:
    operator: AuthIdentity
    identity: AuthIdentity
    other_identity: AuthIdentity
    household_id: uuid.UUID
    other_household_id: uuid.UUID
    address_id: uuid.UUID
    offer_id: uuid.UUID
    pet_id: uuid.UUID
    other_pet_id: uuid.UUID
    order_id: uuid.UUID
    """An order that belongs to other_identity/other_household."""


@pytest.fixture()
async def auth_seed() -> AuthSeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98918{token[:7]}", status="active"
        )
        identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98919{token[:7]}", status="active"
        )
        other_identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98920{token[:7]}", status="active"
        )
        supplier = Supplier(internal_name=f"ws5e-supplier-{token}", country_code="IR", active=True)
        product = Product(name_fa=f"محصول {token}", status="active")
        household = Household(name=f"خانواده {token}")
        other_household = Household(name=f"خانواده دیگر {token}")
        session.add_all(
            [operator, identity, other_identity, supplier, product, household, other_household]
        )
        await session.flush()
        session.add_all(
            [
                HouseholdMembership(
                    household_id=household.id, identity_id=identity.id, role="owner"
                ),
                HouseholdMembership(
                    household_id=other_household.id, identity_id=other_identity.id, role="owner"
                ),
            ]
        )
        address = HouseholdAddress(
            household_id=household.id,
            label="خانه",
            recipient_name="Test User",
            recipient_mobile_e164=identity.mobile_e164,
            province="Tehran",
            city="Tehran",
            address_line="ws5e test address",
            postal_code=None,
            active=True,
        )
        offer = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"WS5E-{token}",
            title_fa="پیشنهاد تست",
            unit_label_fa="کیسه",
            price_irr=1_000_000,
            status="active",
            stock_posture="sourced_after_payment",
            sourcing_route="individual",
            minimum_shelf_life_months=6,
        )
        pet = Pet(household_id=household.id, name="Milo", species="cat", status="active")
        other_pet = Pet(
            household_id=other_household.id, name="Nilo", species="cat", status="active"
        )
        other_order = Order(
            customer_identity_id=other_identity.id,
            household_id=other_household.id,
            status="awaiting_payment",
            currency="IRR",
            merchandise_total_irr=1_000_000,
            checkout_idempotency_key=f"ws5e-foreign-order-{token}",
            delivery_address_snapshot={
                "label": "خانه",
                "recipient_name": "Other",
                "recipient_mobile_e164": other_identity.mobile_e164,
                "province": "Tehran",
                "city": "Tehran",
                "address_line": "other household address",
                "postal_code": None,
            },
        )
        session.add_all([address, offer, pet, other_pet, other_order])
        await session.commit()
        return AuthSeed(
            operator=operator,
            identity=identity,
            other_identity=other_identity,
            household_id=household.id,
            other_household_id=other_household.id,
            address_id=address.id,
            offer_id=offer.id,
            pet_id=pet.id,
            other_pet_id=other_pet.id,
            order_id=other_order.id,
        )


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def test_checkout_rejects_a_foreign_household_id(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], auth_seed: AuthSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: auth_seed.identity

    response = await client.post(
        "/api/v1/checkout/orders",
        json={
            "household_id": str(auth_seed.other_household_id),
            "address_id": str(auth_seed.address_id),
            "items": [{"offer_id": str(auth_seed.offer_id), "quantity": 1}],
        },
        headers={"Idempotency-Key": f"ws5e-checkout-{uuid.uuid4().hex}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "household_not_found"


async def test_reservation_creation_rejects_a_foreign_household_id(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
    auth_seed: AuthSeed,
    reserve_now_enabled: None,
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: auth_seed.identity

    response = await client.post(
        "/api/v1/reservations",
        json={
            "household_id": str(auth_seed.other_household_id),
            "offer_id": str(auth_seed.offer_id),
            "quantity": 1,
        },
        headers={"Idempotency-Key": f"ws5e-reservation-{uuid.uuid4().hex}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "household_not_found"


async def test_order_subroutes_are_non_enumerating_for_a_foreign_order(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], auth_seed: AuthSeed
) -> None:
    """auth_seed.order_id belongs to other_identity/other_household; identity
    must get an identical 404 from every order sub-route, never someone
    else's order data."""
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: auth_seed.identity
    order_id = str(auth_seed.order_id)
    nonexistent_id = str(uuid.uuid4())

    detail = await client.get(f"/api/v1/orders/{order_id}")
    detail_nonexistent = await client.get(f"/api/v1/orders/{nonexistent_id}")
    assert detail.status_code == detail_nonexistent.status_code == 404
    assert detail.json()["error"]["code"] == detail_nonexistent.json()["error"]["code"]

    journey = await client.get(f"/api/v1/orders/{order_id}/journey")
    assert journey.status_code == 404

    delay_ack = await client.post(
        f"/api/v1/orders/{order_id}/delay-acknowledgements",
        headers={"Idempotency-Key": f"ws5e-delay-ack-{uuid.uuid4().hex}"},
    )
    assert delay_ack.status_code == 404

    pet_plan = await client.put(f"/api/v1/orders/{order_id}/pet-plan", json={"lines": []})
    assert pet_plan.status_code == 404

    shelf_life_list = await client.get(f"/api/v1/orders/{order_id}/shelf-life-exceptions")
    assert shelf_life_list.status_code == 404

    cancel = await client.post(
        f"/api/v1/orders/{order_id}/cancel",
        json={"reason": "should never reach this order"},
    )
    assert cancel.status_code == 404


async def test_payment_initiation_is_non_enumerating_for_a_foreign_order(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
    auth_seed: AuthSeed,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PaymentService.initiate enforces ownership inside the service layer
    and returns 409 (not 404) for a foreign/nonexistent/non-awaiting-payment
    order -- a deliberate, documented deviation from the route-boundary 404
    convention (ADR-011). This test locks that behavior down: it must never
    return another household's redirect_url, and the foreign-order and
    nonexistent-order cases must be indistinguishable.
    """
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: auth_seed.identity
    monkeypatch.setattr(
        "app.api.routes.commerce.build_payment_gateway", lambda settings: FakePaymentGateway()
    )

    foreign = await client.post(
        f"/api/v1/orders/{auth_seed.order_id}/payments/zarinpal",
        json={"callback_url": "https://app.test/callback"},
        headers={"Idempotency-Key": f"ws5e-pay-foreign-{uuid.uuid4().hex}"},
    )
    nonexistent = await client.post(
        f"/api/v1/orders/{uuid.uuid4()}/payments/zarinpal",
        json={"callback_url": "https://app.test/callback"},
        headers={"Idempotency-Key": f"ws5e-pay-missing-{uuid.uuid4().hex}"},
    )
    assert foreign.status_code == nonexistent.status_code == 409
    assert "redirect_url" not in foreign.json()
    assert foreign.json()["error"]["code"] == nonexistent.json()["error"]["code"]


async def test_knowledge_pet_detail_is_non_enumerating_for_a_foreign_household(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], auth_seed: AuthSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: auth_seed.identity

    response = await client.get(f"/api/v1/knowledge/pets/{auth_seed.other_pet_id}")
    assert response.status_code == 404


async def test_customer_request_creation_rejects_foreign_household_and_mismatched_order(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], auth_seed: AuthSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: auth_seed.identity

    foreign_household = await client.post(
        "/api/v1/customer-requests",
        json={
            "household_id": str(auth_seed.other_household_id),
            "request_type": "support",
            "message_fa": "این نباید ثبت شود",
            "contact_preference": "in_app",
        },
        headers={"Idempotency-Key": f"ws5e-cr-hh-{uuid.uuid4().hex}"},
    )
    assert foreign_household.status_code == 404
    assert foreign_household.json()["error"]["code"] == "household_not_found"

    # household_id is identity's own (valid), but order_id belongs to a
    # different household entirely -- the mismatch must still be rejected.
    mismatched_order = await client.post(
        "/api/v1/customer-requests",
        json={
            "household_id": str(auth_seed.household_id),
            "order_id": str(auth_seed.order_id),
            "request_type": "support",
            "message_fa": "این نباید ثبت شود",
            "contact_preference": "in_app",
        },
        headers={"Idempotency-Key": f"ws5e-cr-order-{uuid.uuid4().hex}"},
    )
    assert mismatched_order.status_code == 404
    assert mismatched_order.json()["error"]["code"] == "order_not_found"


async def test_operator_routes_reject_a_customer_identity(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], auth_seed: AuthSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: auth_seed.identity
    placeholder = str(uuid.uuid4())

    checks: list[tuple[str, str, dict[str, object] | None]] = [
        (
            "POST",
            f"/api/v1/operator/orders/{placeholder}/deliver",
            {"household_id": placeholder, "reason": "should never be reached by a customer"},
        ),
        (
            "POST",
            f"/api/v1/operator/orders/{placeholder}/late-credit",
            {"reason": "should never be reached by a customer"},
        ),
        (
            "POST",
            f"/api/v1/operator/orders/{placeholder}/fulfillment",
            {"event_type": "in_transit", "reason": "should never be reached by a customer"},
        ),
        (
            "POST",
            f"/api/v1/operator/payments/{placeholder}/reconcile",
            {"reason": "should never be reached by a customer"},
        ),
        (
            "POST",
            f"/api/v1/operator/privacy/requests/{placeholder}/disable",
            {"reason": "should never be reached by a customer"},
        ),
        ("GET", f"/api/v1/operator/customers/{placeholder}/overview", None),
        ("GET", "/api/v1/operator/audit/export", None),
        ("GET", "/api/v1/operator/reservations", None),
        ("GET", "/api/v1/operator/shelf-life-exceptions", None),
        ("GET", "/api/v1/operator/price-intelligence/sources", None),
    ]
    for method, path, body in checks:
        response = await client.request(method, path, json=body)
        assert response.status_code == 403, f"{method} {path} returned {response.status_code}"
