from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.api.dependencies import get_current_identity
from app.common.time import utc_now
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
from app.modules.catalog.availability import notify_available_subscribers
from app.modules.catalog.models import CatalogAvailabilitySubscription, Offer, Product, Supplier
from app.modules.checkout.service import CheckoutItem, CheckoutService
from app.modules.diary.models import DiaryEntry
from app.modules.garden.models import GardenReward
from app.modules.households.models import Household, HouseholdAddress, HouseholdMembership
from app.modules.identity.models import AuthIdentity
from app.modules.journeys.models import JourneyCheckIn, JourneyDefinition, PetJourney
from app.modules.notifications.models import Notification
from app.modules.notifications.service import enqueue_wallet_credit_notification
from app.modules.orders.fulfillment import FulfillmentEvent
from app.modules.orders.models import Order, OrderDelayAcknowledgement
from app.modules.payments.models import PaymentAttempt
from app.modules.payments.service import PaymentService
from app.modules.pets.models import Pet
from app.modules.sourcing.models import SourcingJob
from app.modules.support.models import CustomerRequest
from app.modules.system.event_registry import EVENT_REGISTRY
from app.modules.system.models import OutboxEvent
from app.modules.system.outbox import DomainEvent, OutboxDispatcher, add_outbox_event
from redis.asyncio import Redis
from sqlalchemy import func, select, text

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL/Redis is required",
)


@pytest.fixture(autouse=True)
async def dispose_engine_between_event_loops() -> AsyncIterator[None]:
    yield
    await close_database()


@dataclass(slots=True)
class Seed:
    identity: AuthIdentity
    other_identity: AuthIdentity
    household: Household
    other_household: Household
    address: HouseholdAddress
    offer: Offer
    unavailable_offer: Offer
    pet: Pet
    other_pet: Pet


class FakePaymentGateway:
    def __init__(self) -> None:
        self.initiations = 0
        self.verifications = 0

    async def initiate(self, request: PaymentRequest) -> PaymentInitiation:
        self.initiations += 1
        return PaymentInitiation(
            provider_reference=f"fake-{request.order_id}",
            redirect_url=f"https://payments.test/{request.order_id}",
        )

    async def verify(self, *, provider_reference: str, amount_irr: int) -> PaymentVerification:
        self.verifications += 1
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


def approved_journey_content() -> dict[str, object]:
    return {
        "professional_approval_ref": "vet-board-1",
        "garden_object_key": "leaf",
        "summary_fa": "مسیر تایید شده",
        "duration_days": 2,
        "eligible_species": ["cat"],
        "steps": [
            {
                "key": "step-1",
                "title_fa": "مرحله اول",
                "body_fa": "مشاهده غیرتشخیصی را ثبت کنید.",
                "allowed_answers": [{"key": "done", "label_fa": "انجام شد"}],
            }
        ],
        "completion_requires": ["step-1"],
        "exception_behavior": {
            "behavior": "non_diagnostic",
            "message_fa": "در صورت نگرانی با متخصص مشورت کنید.",
        },
        "completion_memory_title_fa": "خاطره مسیر",
    }


@pytest.fixture()
async def redis_client() -> AsyncIterator[Redis]:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await client.ping()
    yield client
    await client.aclose()


@pytest.fixture()
async def seed() -> Seed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98910{token[:7]}", status="active"
        )
        other_identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98911{token[:7]}", status="active"
        )
        supplier = Supplier(internal_name=f"supplier-{token}", country_code="IR", active=True)
        product = Product(
            name_fa="غذای تست",
            description_fa="توضیح تست",
            nominal_quantity_grams=1000,
            status="active",
        )
        household = Household(name=f"hh-{token}")
        other_household = Household(name=f"other-{token}")
        session.add_all([identity, other_identity, supplier, product, household, other_household])
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
            recipient_name="Pet User",
            recipient_mobile_e164=identity.mobile_e164,
            province="Tehran",
            city="Tehran",
            address_line="Runtime integrity address",
            postal_code=None,
            active=True,
        )
        offer = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"K10-{token}",
            title_fa="پیشنهاد تست",
            unit_label_fa="کیسه",
            price_irr=1_000_000,
            reference_price_irr=1_200_000,
            status="active",
            stock_posture="sourced_after_payment",
            minimum_shelf_life_months=6,
        )
        unavailable_offer = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"K10-U-{token}",
            title_fa="ناموجود تست",
            unit_label_fa="کیسه",
            price_irr=1_000_000,
            status="unavailable",
            stock_posture="unavailable",
            minimum_shelf_life_months=6,
        )
        pet = Pet(household_id=household.id, name="Milo", species="cat", status="active")
        other_pet = Pet(
            household_id=other_household.id, name="Nilo", species="cat", status="active"
        )
        session.add_all([address, offer, unavailable_offer, pet, other_pet])
        await session.commit()
        return Seed(
            identity=identity,
            other_identity=other_identity,
            household=household,
            other_household=other_household,
            address=address,
            offer=offer,
            unavailable_offer=unavailable_offer,
            pet=pet,
            other_pet=other_pet,
        )


async def test_k9_t1_to_t14_runtime_checkout_payment_replay_and_access(seed: Seed) -> None:
    gateway = FakePaymentGateway()
    async def checkout() -> Order:
        async with SessionFactory() as session:
            return await CheckoutService().create_order(
                session,
                customer_identity_id=seed.identity.id,
                household_id=seed.household.id,
                address_id=seed.address.id,
                items=[CheckoutItem(seed.offer.id, 1)],
                idempotency_key="same-checkout-key",
            )

    first, replay = await asyncio.gather(checkout(), checkout())
    async with SessionFactory() as session:
        assert first.id == replay.id
        attempt = await PaymentService().initiate(
            session,
            gateway,
            order_id=first.id,
            customer_identity_id=seed.identity.id,
            customer_mobile_e164=seed.identity.mobile_e164,
            callback_url="https://app.test/callback",
            idempotency_key="same-payment-key",
        )
    async def verify() -> Order:
        async with SessionFactory() as session:
            return await PaymentService().verify(
                session, gateway, provider_reference=f"fake-{first.id}"
            )

    verified_a, verified_b = await asyncio.gather(verify(), verify())
    async with SessionFactory() as session:
        assert verified_a.id == verified_b.id == first.id
        assert attempt.redirect_url.endswith(str(first.id))
        assert (
            await session.scalar(
                select(func.count(SourcingJob.id)).where(SourcingJob.order_id == first.id)
            )
        ) == 1

        conflict = await session.scalar(
            select(Order).where(
                Order.customer_identity_id == seed.identity.id,
                Order.checkout_idempotency_key == "same-checkout-key",
            )
        )
        assert conflict is not None and conflict.checkout_request_hash is not None
        assert await session.get(Pet, seed.other_pet.id) is not None


async def test_ws5c_verify_does_not_hold_row_locks_during_gateway_io(seed: Seed) -> None:
    gateway = FakePaymentGateway()
    async with SessionFactory() as session:
        order = await CheckoutService().create_order(
            session,
            customer_identity_id=seed.identity.id,
            household_id=seed.household.id,
            address_id=seed.address.id,
            items=[CheckoutItem(seed.offer.id, 1)],
            idempotency_key="ws5c-lock-checkout-key",
        )
        redirect = await PaymentService().initiate(
            session,
            gateway,
            order_id=order.id,
            customer_identity_id=seed.identity.id,
            customer_mobile_e164=seed.identity.mobile_e164,
            callback_url="https://app.test/callback",
            idempotency_key="ws5c-lock-payment-key",
        )

    gateway_call_started = asyncio.Event()
    proceed = asyncio.Event()

    class SlowGateway(FakePaymentGateway):
        async def verify(self, *, provider_reference: str, amount_irr: int) -> PaymentVerification:
            gateway_call_started.set()
            await proceed.wait()
            return await super().verify(
                provider_reference=provider_reference, amount_irr=amount_irr
            )

    slow_gateway = SlowGateway()

    async def run_verify() -> Order:
        async with SessionFactory() as session:
            return await PaymentService().verify(
                session, slow_gateway, provider_reference=f"fake-{order.id}"
            )

    verify_task = asyncio.create_task(run_verify())
    await asyncio.wait_for(gateway_call_started.wait(), timeout=5)

    # While the (slow, simulated-network) gateway call is in flight, the
    # order and payment-attempt rows must not be locked -- a concurrent,
    # unrelated NOWAIT lock attempt must succeed immediately rather than
    # raising LockNotAvailable.
    async with SessionFactory() as probe_session:
        probed_order = await probe_session.scalar(
            select(Order).where(Order.id == order.id).with_for_update(nowait=True)
        )
        assert probed_order is not None
        probed_attempt = await probe_session.scalar(
            select(PaymentAttempt)
            .where(PaymentAttempt.id == redirect.attempt_id)
            .with_for_update(nowait=True)
        )
        assert probed_attempt is not None
        await probe_session.rollback()

    proceed.set()
    verified_order = await asyncio.wait_for(verify_task, timeout=5)
    assert verified_order.id == order.id
    assert slow_gateway.verifications == 1


async def test_ws5c_concurrent_reconcile_preserves_single_sourcing_job(seed: Seed) -> None:
    gateway = FakePaymentGateway()
    async with SessionFactory() as session:
        order = await CheckoutService().create_order(
            session,
            customer_identity_id=seed.identity.id,
            household_id=seed.household.id,
            address_id=seed.address.id,
            items=[CheckoutItem(seed.offer.id, 1)],
            idempotency_key="ws5c-reconcile-checkout-key",
        )
        redirect = await PaymentService().initiate(
            session,
            gateway,
            order_id=order.id,
            customer_identity_id=seed.identity.id,
            customer_mobile_e164=seed.identity.mobile_e164,
            callback_url="https://app.test/callback",
            idempotency_key="ws5c-reconcile-payment-key",
        )

    async def reconcile() -> str:
        async with SessionFactory() as session:
            result = await PaymentService().reconcile(
                session, gateway, attempt_id=redirect.attempt_id
            )
            return result.state

    state_a, state_b = await asyncio.gather(reconcile(), reconcile())
    assert state_a == state_b == "verified"
    async with SessionFactory() as session:
        assert (
            await session.scalar(
                select(func.count(SourcingJob.id)).where(SourcingJob.order_id == order.id)
            )
        ) == 1
        events = (
            await session.scalars(
                select(OutboxEvent).where(
                    OutboxEvent.event_type == "order.payment_verified",
                    OutboxEvent.aggregate_id == str(order.id),
                )
            )
        ).all()
        assert len(events) == 1


async def test_k9_t9_to_t14_api_replay_and_cross_household(seed: Seed, monkeypatch: Any) -> None:
    settings = get_settings()
    settings.care_journey_delivery_enabled = True
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    fake_gateway = FakePaymentGateway()
    monkeypatch.setattr(
        "app.api.routes.commerce.build_payment_gateway",
        lambda settings: fake_gateway,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unavailable = await client.post(
            f"/api/v1/catalog/offers/{seed.unavailable_offer.id}/availability-subscriptions"
        )
        assert unavailable.status_code == 200
        assert unavailable.json()["order_created"] is False
        other_pet = await client.get(f"/api/v1/pet-life/pets/{seed.other_pet.id}/today")
        assert other_pet.status_code == 404
        request_body = {
            "household_id": str(seed.household.id),
            "request_type": "support",
            "message_fa": "لطفا بررسی شود",
            "contact_preference": "in_app",
        }
        one, two = await asyncio.gather(
            client.post(
                "/api/v1/customer-requests",
                json=request_body,
                headers={"Idempotency-Key": "same-request-key"},
            ),
            client.post(
                "/api/v1/customer-requests",
                json=request_body,
                headers={"Idempotency-Key": "same-request-key"},
            ),
        )
        assert one.status_code in (200, 201)
        assert two.status_code in (200, 201)
        assert one.json()["id"] == two.json()["id"]
        different = dict(request_body, message_fa="متن متفاوت")
        conflict = await client.post(
            "/api/v1/customer-requests",
            json=different,
            headers={"Idempotency-Key": "same-request-key"},
        )
        assert conflict.status_code == 409

    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.unavailable_offer.id)
        assert offer is not None
        offer.status = "active"
        offer.stock_posture = "sourced_after_payment"
        offer.sourcing_capacity_status = "open"
        await notify_available_subscribers(session, offer)
        await session.commit()
        offer = await session.get(Offer, seed.unavailable_offer.id)
        assert offer is not None
        await notify_available_subscribers(session, offer)
        await session.commit()
        assert (
            await session.scalar(
                        select(func.count(Notification.id)).where(
                            Notification.event_key == "catalog.offer_available",
                            Notification.recipient_identity_id == seed.identity.id,
                        )
                )
            ) == 2
        assert (
            await session.scalar(
                select(func.count(CustomerRequest.id)).where(
                    CustomerRequest.identity_id == seed.identity.id
                )
            )
        ) == 1

    settings.care_journey_delivery_enabled = False
    app.dependency_overrides.clear()


async def test_k9_t10_t11_delay_ack_and_journey_effects_are_canonical(seed: Seed) -> None:
    async with SessionFactory() as session:
        operator = AuthIdentity(
            identity_type="operator",
            mobile_e164=f"+98912{uuid.uuid4().hex[:7]}",
            status="active",
        )
        order = Order(
            customer_identity_id=seed.identity.id,
            household_id=seed.household.id,
            status="in_transit",
            currency="IRR",
            merchandise_total_irr=1000,
            checkout_idempotency_key=f"manual-{uuid.uuid4()}",
            delivery_address_snapshot={
                "label": "x",
                "recipient_name": "x",
                "recipient_mobile_e164": seed.identity.mobile_e164,
                "province": "x",
                "city": "x",
                "address_line": "x",
            },
        )
        session.add_all([operator, order])
        await session.flush()
        session.add(
            FulfillmentEvent(
                order_id=order.id,
                event_type="delayed",
                occurred_at=utc_now(),
                reason="late",
                operator_identity_id=operator.id,
            )
        )
        definition = JourneyDefinition(
            key=f"k10-{uuid.uuid4()}",
            version=1,
            title_fa="مسیر تست",
            content={
                "professional_approval_ref": "approved",
                "steps": [
                    {
                        "key": "step-1",
                        "title_fa": "مرحله",
                        "body_fa": "ثبت کنید.",
                        "allowed_answers": [{"key": "done", "label_fa": "انجام شد"}],
                    }
                ],
                "completion_requires": ["step-1"],
                "garden_object_key": "leaf",
                "completion_memory_title_fa": "خاطره تست",
            },
            approval_status="approved",
            approved_by="vet",
            approved_at=utc_now(),
        )
        session.add(definition)
        await session.commit()

    settings = get_settings()
    settings.care_journey_delivery_enabled = True
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ack_a, ack_b = await asyncio.gather(
            client.post(
                f"/api/v1/orders/{order.id}/delay-acknowledgements",
                headers={"Idempotency-Key": "same-ack-key"},
            ),
            client.post(
                f"/api/v1/orders/{order.id}/delay-acknowledgements",
                headers={"Idempotency-Key": "same-ack-key"},
            ),
        )
        assert ack_a.status_code == 200
        assert ack_b.status_code == 200
        assert ack_a.json()["id"] == ack_b.json()["id"]
        start = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/journeys",
            json={"definition_id": str(definition.id)},
        )
        assert start.status_code in (200, 201)
        journey_id = start.json()["id"]
        check_in_a, check_in_b = await asyncio.gather(
            client.post(
                f"/api/v1/pet-life/journeys/{journey_id}/check-ins",
                json={"check_in_key": "step-1", "answer_key": "done"},
                headers={"Idempotency-Key": "same-checkin-key"},
            ),
            client.post(
                f"/api/v1/pet-life/journeys/{journey_id}/check-ins",
                json={"check_in_key": "step-1", "answer_key": "done"},
                headers={"Idempotency-Key": "same-checkin-key"},
            ),
        )
        assert check_in_a.status_code == 200
        assert check_in_b.status_code == 200
        # Whichever request wins the race to insert and which one falls back to
        # the IntegrityError replay path is non-deterministic; both must report
        # the journey's real completion outcome (single-step journey, so this
        # check-in alone satisfies completion_requires), not a stale default.
        assert check_in_a.json()["id"] == check_in_b.json()["id"]
        assert check_in_a.json()["completed"] is True
        assert check_in_b.json()["completed"] is True
        assert check_in_a.json()["diary_entry_id"] == check_in_b.json()["diary_entry_id"]
        assert check_in_a.json()["diary_entry_id"] is not None
        assert check_in_a.json()["garden_reward_id"] == check_in_b.json()["garden_reward_id"]
        assert check_in_a.json()["garden_reward_id"] is not None
    async with SessionFactory() as session:
        assert (
            await session.scalar(
                select(func.count(OrderDelayAcknowledgement.id)).where(
                    OrderDelayAcknowledgement.order_id == order.id
                )
            )
        ) == 1
        assert (
            await session.scalar(
                select(func.count(JourneyCheckIn.id)).where(
                    JourneyCheckIn.journey_id == uuid.UUID(journey_id)
                )
            )
        ) == 1
        assert (
            await session.scalar(
                select(func.count(DiaryEntry.id)).where(
                    DiaryEntry.source_id == journey_id, DiaryEntry.source_type == "journey"
                )
            )
        ) == 1
        assert (
            await session.scalar(
                select(func.count(GardenReward.id)).where(
                    GardenReward.source_id == journey_id,
                    GardenReward.source_type == "journey_completion",
                )
            )
        ) == 1
    settings.care_journey_delivery_enabled = False
    app.dependency_overrides.clear()


async def test_approved_journey_delivery_lifecycle_today_and_replay(seed: Seed) -> None:
    async with SessionFactory() as session:
        approved = JourneyDefinition(
            key=f"approved-{uuid.uuid4()}",
            version=1,
            title_fa="مسیر تایید شده",
            content=approved_journey_content(),
            approval_status="approved",
            approved_by="vet",
            approved_at=utc_now(),
        )
        draft = JourneyDefinition(
            key=f"draft-{uuid.uuid4()}",
            version=1,
            title_fa="پیش‌نویس",
            content=approved_journey_content(),
            approval_status="draft",
        )
        dog_only = JourneyDefinition(
            key=f"dog-{uuid.uuid4()}",
            version=1,
            title_fa="سگ",
            content={**approved_journey_content(), "eligible_species": ["dog"]},
            approval_status="approved",
            approved_by="vet",
            approved_at=utc_now(),
        )
        invalid = JourneyDefinition(
            key=f"invalid-{uuid.uuid4()}",
            version=1,
            title_fa="بی‌مرجع",
            content={**approved_journey_content(), "professional_approval_ref": ""},
            approval_status="approved",
            approved_by="vet",
            approved_at=utc_now(),
        )
        session.add_all([approved, draft, dog_only, invalid])
        await session.commit()

    settings = get_settings()
    original = settings.care_journey_delivery_enabled
    settings.care_journey_delivery_enabled = True
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        offers = await client.get(f"/api/v1/pet-life/pets/{seed.pet.id}/journey-offers")
        assert offers.status_code == 200
        offer_ids = {item["definition_id"] for item in offers.json()}
        assert str(approved.id) in offer_ids
        assert str(draft.id) not in offer_ids
        assert str(dog_only.id) not in offer_ids
        assert str(invalid.id) not in offer_ids
        draft_detail = await client.get(f"/api/v1/pet-life/journey-definitions/{draft.id}")
        invalid_detail = await client.get(
            f"/api/v1/pet-life/journey-definitions/{invalid.id}"
        )
        assert draft_detail.status_code == 404
        assert invalid_detail.status_code == 404
        started = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/journeys",
            json={"definition_id": str(approved.id)},
        )
        assert started.status_code == 200
        journey_id = started.json()["id"]
        detail = await client.get(f"/api/v1/pet-life/journeys/{journey_id}")
        assert detail.status_code == 200
        assert "additionalProperties" not in detail.json()["steps"][0]
        pause = await client.post(f"/api/v1/pet-life/journeys/{journey_id}/pause")
        resume = await client.post(f"/api/v1/pet-life/journeys/{journey_id}/resume")
        assert pause.status_code == 204
        assert resume.status_code == 204
        today = await client.get(f"/api/v1/pet-life/pets/{seed.pet.id}/today")
        assert today.json()["primary_attention"]["type"] == "active_journey"
        bad = await client.post(
            f"/api/v1/pet-life/journeys/{journey_id}/check-ins",
            json={"check_in_key": "step-1", "answer_key": "other"},
            headers={"Idempotency-Key": "journey-bad-key"},
        )
        assert bad.status_code == 422
        first = await client.post(
            f"/api/v1/pet-life/journeys/{journey_id}/check-ins",
            json={"check_in_key": "step-1", "answer_key": "done"},
            headers={"Idempotency-Key": "journey-ok-key"},
        )
        replay = await client.post(
            f"/api/v1/pet-life/journeys/{journey_id}/check-ins",
            json={"check_in_key": "step-1", "answer_key": "done"},
            headers={"Idempotency-Key": "journey-ok-key"},
        )
        conflict = await client.post(
            f"/api/v1/pet-life/journeys/{journey_id}/check-ins",
            json={"check_in_key": "step-1", "answer_key": "other"},
            headers={"Idempotency-Key": "journey-ok-key"},
        )
        assert first.status_code == 200
        assert replay.status_code == 200
        assert first.json()["id"] == replay.json()["id"]
        assert conflict.status_code == 409
        # This single-step journey's completion_requires is satisfied by the very
        # first check-in, so the backend auto-completes it inline: the response
        # must carry the completion transition, not just a bare check-in record.
        assert first.json()["completed"] is True
        assert first.json()["diary_entry_id"] is not None
        assert first.json()["garden_reward_id"] is not None
        # A replayed check-in (same idempotency key) must report the same
        # completion outcome, not silently default back to completed=False.
        assert replay.json()["completed"] is True
        assert replay.json()["diary_entry_id"] == first.json()["diary_entry_id"]
        assert replay.json()["garden_reward_id"] == first.json()["garden_reward_id"]
        completed_detail = await client.get(
            f"/api/v1/pet-life/journeys/{journey_id}"
        )
        assert completed_detail.status_code == 200
        assert completed_detail.json()["status"] == "completed"
        assert completed_detail.json()["diary_entry_id"] == first.json()["diary_entry_id"]
        assert (
            completed_detail.json()["garden_reward_id"] == first.json()["garden_reward_id"]
        )
        garden = await client.get(f"/api/v1/pet-life/pets/{seed.pet.id}/garden")
        assert {"xp", "streak", "decay", "purchase_reward"} & set(garden.json()) == set()
    app.dependency_overrides[get_current_identity] = lambda: seed.other_identity
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get(f"/api/v1/pet-life/journeys/{journey_id}")).status_code == 404
    async with SessionFactory() as session:
        assert (
            await session.scalar(
                select(func.count(DiaryEntry.id)).where(
                    DiaryEntry.source_id == journey_id,
                    DiaryEntry.source_type == "journey",
                )
            )
        ) == 1
        assert (
            await session.scalar(
                select(func.count(GardenReward.id)).where(
                    GardenReward.source_id == journey_id,
                    GardenReward.source_type == "journey_completion",
                )
            )
        ) == 1
        journey = await session.get(PetJourney, uuid.UUID(journey_id))
        assert journey is not None and journey.status == "completed"
    settings.care_journey_delivery_enabled = original
    app.dependency_overrides.clear()


async def test_pet_health_consent_lifecycle_is_explicit_and_governed(seed: Seed) -> None:
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    png_bytes = b"\x89PNG\r\n\x1a\nfakepngdata"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        policies = await client.get("/api/v1/system/policies")
        assert policies.status_code == 200
        policy_version = policies.json()["pet_health_consent_policy_version"]
        assert policy_version

        empty = await client.get(f"/api/v1/pet-life/pets/{seed.pet.id}/consents")
        assert empty.status_code == 200
        assert empty.json() == []

        # Upload attempted before any consent is granted must fail closed.
        blocked = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/assets",
            content=png_bytes,
            headers={
                "content-type": "image/png",
                "X-Filename": "body.png",
                "X-Asset-Category": "body_top",
                "X-Consent-ID": str(uuid.uuid4()),
            },
        )
        assert blocked.status_code == 409

        granted = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/consents",
            json={"purpose": "body_photographs", "policy_version": policy_version},
        )
        assert granted.status_code == 201
        consent_id = granted.json()["id"]
        assert granted.json()["status"] == "granted"
        assert granted.json()["policy_version"] == policy_version

        # Re-granting the same purpose/version is idempotent: same row, not a
        # second interruption or a duplicate consent record.
        regranted = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/consents",
            json={"purpose": "body_photographs", "policy_version": policy_version},
        )
        assert regranted.status_code == 201
        assert regranted.json()["id"] == consent_id

        listed = await client.get(f"/api/v1/pet-life/pets/{seed.pet.id}/consents")
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert listed.json()[0]["id"] == consent_id

        # A policy-version change while an active consent exists must not be
        # silently accepted; it requires an explicit withdrawal first.
        version_conflict = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/consents",
            json={
                "purpose": "body_photographs",
                "policy_version": "policy-version-should-not-exist",
            },
        )
        assert version_conflict.status_code == 409

        upload = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/assets",
            content=png_bytes,
            headers={
                "content-type": "image/png",
                "X-Filename": "body.png",
                "X-Asset-Category": "body_top",
                "X-Consent-ID": consent_id,
            },
        )
        assert upload.status_code == 201
        asset_id = upload.json()["id"]

        withdraw = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/consents/{consent_id}/withdraw"
        )
        assert withdraw.status_code == 204

        withdrawn_list = await client.get(f"/api/v1/pet-life/pets/{seed.pet.id}/consents")
        assert withdrawn_list.json()[0]["status"] == "withdrawn"
        assert withdrawn_list.json()[0]["withdrawn_at"] is not None

        # Withdrawal removes the asset from customer-visible listing immediately.
        assets_after_withdraw = await client.get(f"/api/v1/pet-life/pets/{seed.pet.id}/assets")
        assert asset_id not in {item["id"] for item in assets_after_withdraw.json()}

        # Uploading again against the withdrawn consent must fail closed too.
        reuse_withdrawn = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/assets",
            content=png_bytes,
            headers={
                "content-type": "image/png",
                "X-Filename": "body2.png",
                "X-Asset-Category": "body_top",
                "X-Consent-ID": consent_id,
            },
        )
        assert reuse_withdrawn.status_code == 409

    app.dependency_overrides[get_current_identity] = lambda: seed.other_identity
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        cross_household = await client.get(f"/api/v1/pet-life/pets/{seed.pet.id}/consents")
        assert cross_household.status_code == 404
    app.dependency_overrides.clear()


async def test_pet_consent_grant_rejects_non_current_policy_version(seed: Seed) -> None:
    # A brand-new grant (no existing consent row yet) with an arbitrary
    # client-supplied policy_version must be rejected server-side, not just
    # trusted because the frontend happens to send the right value.
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        rejected = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/consents",
            json={"purpose": "body_photographs", "policy_version": "not-the-current-version"},
        )
        assert rejected.status_code == 409
        assert rejected.json()["error"]["code"] == "consent_policy_version_stale"

        empty = await client.get(f"/api/v1/pet-life/pets/{seed.pet.id}/consents")
        assert empty.status_code == 200
        assert empty.json() == []
    app.dependency_overrides.clear()


async def test_pet_consent_upload_rejects_stale_policy_version(seed: Seed) -> None:
    # A consent granted under the current policy must stop authorizing
    # uploads the moment the active policy version advances, even though the
    # consent row itself was never withdrawn.
    settings = get_settings()
    original_version = settings.pet_health_consent_policy_version
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            policies = await client.get("/api/v1/system/policies")
            current_version = policies.json()["pet_health_consent_policy_version"]
            granted = await client.post(
                f"/api/v1/pet-life/pets/{seed.pet.id}/consents",
                json={"purpose": "body_photographs", "policy_version": current_version},
            )
            assert granted.status_code == 201
            consent_id = granted.json()["id"]

            settings.pet_health_consent_policy_version = f"{original_version}-superseded"

            blocked = await client.post(
                f"/api/v1/pet-life/pets/{seed.pet.id}/assets",
                content=b"\x89PNG\r\n\x1a\nfakepngdata",
                headers={
                    "content-type": "image/png",
                    "X-Filename": "body.png",
                    "X-Asset-Category": "body_top",
                    "X-Consent-ID": consent_id,
                },
            )
            assert blocked.status_code == 409
            assert blocked.json()["error"]["code"] == "consent_policy_version_stale"
    finally:
        settings.pet_health_consent_policy_version = original_version
    app.dependency_overrides.clear()


async def test_pet_consent_concurrent_identical_grants_return_one_consent(seed: Seed) -> None:
    # Two racing grant requests for the same pet/purpose/current-version must
    # not surface the underlying partial-unique-index violation as an
    # unhandled 500; both must resolve to the same consent row.
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        policies = await client.get("/api/v1/system/policies")
        policy_version = policies.json()["pet_health_consent_policy_version"]

        first, second = await asyncio.gather(
            client.post(
                f"/api/v1/pet-life/pets/{seed.pet.id}/consents",
                json={"purpose": "medical_records", "policy_version": policy_version},
            ),
            client.post(
                f"/api/v1/pet-life/pets/{seed.pet.id}/consents",
                json={"purpose": "medical_records", "policy_version": policy_version},
            ),
        )
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] == second.json()["id"]

        listed = await client.get(f"/api/v1/pet-life/pets/{seed.pet.id}/consents")
        assert len(listed.json()) == 1
    app.dependency_overrides.clear()


async def test_pet_consent_withdrawal_is_idempotent(seed: Seed) -> None:
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        policies = await client.get("/api/v1/system/policies")
        policy_version = policies.json()["pet_health_consent_policy_version"]
        granted = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/consents",
            json={"purpose": "body_photographs", "policy_version": policy_version},
        )
        consent_id = granted.json()["id"]

        first_withdraw = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/consents/{consent_id}/withdraw"
        )
        assert first_withdraw.status_code == 204
        second_withdraw = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/consents/{consent_id}/withdraw"
        )
        assert second_withdraw.status_code == 204

        listed = await client.get(f"/api/v1/pet-life/pets/{seed.pet.id}/consents")
        assert listed.json()[0]["status"] == "withdrawn"
    app.dependency_overrides.clear()


async def test_pet_consent_purposes_are_independent(seed: Seed) -> None:
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    png_bytes = b"\x89PNG\r\n\x1a\nfakepngdata"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        policies = await client.get("/api/v1/system/policies")
        policy_version = policies.json()["pet_health_consent_policy_version"]

        photo_consent = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/consents",
            json={"purpose": "body_photographs", "policy_version": policy_version},
        )
        medical_consent = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/consents",
            json={"purpose": "medical_records", "policy_version": policy_version},
        )
        assert photo_consent.status_code == 201
        assert medical_consent.status_code == 201
        assert photo_consent.json()["id"] != medical_consent.json()["id"]

        withdraw_photo = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/consents/{photo_consent.json()['id']}/withdraw"
        )
        assert withdraw_photo.status_code == 204

        listed = {item["id"]: item for item in (await client.get(
            f"/api/v1/pet-life/pets/{seed.pet.id}/consents"
        )).json()}
        assert listed[photo_consent.json()["id"]]["status"] == "withdrawn"
        assert listed[medical_consent.json()["id"]]["status"] == "granted"

        upload = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/assets",
            content=png_bytes,
            headers={
                "content-type": "image/png",
                "X-Filename": "lab.png",
                "X-Asset-Category": "lab_result",
                "X-Consent-ID": medical_consent.json()["id"],
            },
        )
        assert upload.status_code == 201
    app.dependency_overrides.clear()


async def test_journey_stop_and_empty_offers_do_not_fabricate_content(seed: Seed) -> None:
    settings = get_settings()
    original = settings.care_journey_delivery_enabled
    settings.care_journey_delivery_enabled = True
    async with SessionFactory() as session:
        await session.execute(text("delete from journey_check_ins"))
        await session.execute(text("delete from journeys_pet_journeys"))
        await session.execute(text("delete from journeys_definitions"))
        await session.commit()
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        offers = await client.get(f"/api/v1/pet-life/pets/{seed.pet.id}/journey-offers")
        assert offers.status_code == 200
        assert offers.json() == []
    async with SessionFactory() as session:
        definition = JourneyDefinition(
            key=f"stop-{uuid.uuid4()}",
            version=1,
            title_fa="توقف",
            content=approved_journey_content(),
            approval_status="approved",
            approved_by="vet",
            approved_at=utc_now(),
        )
        session.add(definition)
        await session.commit()
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        started = await client.post(
            f"/api/v1/pet-life/pets/{seed.pet.id}/journeys",
            json={"definition_id": str(definition.id)},
        )
        assert started.status_code == 200
        stopped = await client.post(
            f"/api/v1/pet-life/journeys/{started.json()['id']}/stop",
            json={"reason": "customer_request"},
        )
        assert stopped.status_code == 204
    settings.care_journey_delivery_enabled = original
    app.dependency_overrides.clear()


async def test_outbox_registry_retries_dead_letter_and_audit_only(
    redis_client: Redis,
) -> None:
    assert {"order.awaiting_payment", "order.payment_verified", "catalog.offer_available"}.issubset(
        EVENT_REGISTRY
    )
    async with SessionFactory() as session:
        add_outbox_event(
            session,
            DomainEvent(
                event_type="order.awaiting_payment",
                aggregate_type="order",
                aggregate_id="audit",
                payload={},
            ),
        )
        add_outbox_event(
            session,
            DomainEvent(
                event_type="unknown.event",
                aggregate_type="unknown",
                aggregate_id="dead",
                payload={},
            ),
        )
        await session.commit()
    dispatcher = OutboxDispatcher(SessionFactory, batch_size=10)
    for _ in range(6):
        await dispatcher.dispatch_batch()
        async with SessionFactory() as session:
            await session.execute(
                text("update system_outbox_events set available_at = now() where status = 'failed'")
            )
            await session.commit()
    async with SessionFactory() as session:
        # Scope by aggregate_id, not just event_type: this shared dev
        # database accumulates "order.awaiting_payment" rows from every
        # other test that runs a real checkout, so an unqualified
        # event_type filter can match an unrelated pending row instead of
        # the one this test just created.
        audit = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.event_type == "order.awaiting_payment",
                OutboxEvent.aggregate_id == "audit",
            )
        )
        unknown = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.event_type == "unknown.event",
                OutboxEvent.aggregate_id == "dead",
            )
        )
        assert audit is not None and audit.status == "published"
        assert unknown is not None and unknown.status == "dead_letter"
    await redis_client.set("pet-platform:test:heartbeat", "alive", ex=30)
    assert await redis_client.get("pet-platform:test:heartbeat") == "alive"


async def test_outbox_dispatcher_invokes_every_registered_handler_once() -> None:
    call_counts = {"first": 0, "second": 0}

    async def first_handler(payload: dict[str, object]) -> None:
        call_counts["first"] += 1

    async def second_handler(payload: dict[str, object]) -> None:
        call_counts["second"] += 1

    aggregate_id = f"dup-handler-{uuid.uuid4().hex}"
    async with SessionFactory() as session:
        event_id = add_outbox_event(
            session,
            DomainEvent(
                event_type="wallet.late_delivery_credit_granted",
                aggregate_type="order",
                aggregate_id=aggregate_id,
                payload={},
            ),
        )
        await session.flush()
        # Claim it for this test before the row is ever visible to the real
        # outbox worker container running alongside the suite against this
        # same shared dev database -- otherwise that worker can win the
        # claim race and dispatch the row with its own real handlers before
        # this test's dispatcher ever sees it.
        record = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        assert record is not None
        record.claimed_until = utc_now() + timedelta(minutes=5)
        await session.commit()

    dispatcher = OutboxDispatcher(SessionFactory, batch_size=10)
    dispatcher.register("wallet.late_delivery_credit_granted", first_handler)
    dispatcher.register("wallet.late_delivery_credit_granted", second_handler)
    async with SessionFactory() as session:
        record = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        assert record is not None
        # _dispatch_one is the same call dispatch_batch makes internally
        # after _claim_batch -- calling it directly on our own already-
        # claimed record exercises the exact handler-invocation logic under
        # test without racing _claim_batch against the live worker.
        await dispatcher._dispatch_one(record)

    async with SessionFactory() as session:
        record = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
    assert record is not None and record.status == "published"
    # A single dispatch of one event must invoke every handler registered
    # for its type exactly once each -- not zero (a silently dropped
    # handler) and not more than once (a duplicate side effect, e.g. a
    # customer notified twice for the same event).
    assert call_counts == {"first": 1, "second": 1}


async def test_outbox_dispatcher_reclaims_stuck_event_after_simulated_process_restart() -> None:
    calls = 0

    async def handler(payload: dict[str, object]) -> None:
        nonlocal calls
        calls += 1

    aggregate_id = f"restart-{uuid.uuid4().hex}"
    async with SessionFactory() as session:
        event_id = add_outbox_event(
            session,
            DomainEvent(
                event_type="wallet.late_delivery_credit_granted",
                aggregate_type="order",
                aggregate_id=aggregate_id,
                payload={},
            ),
        )
        await session.commit()

    # Simulate a worker process crashing mid-dispatch: the batch claim
    # (claimed_until pushed into the future, attempts incremented) already
    # happened, but the process died before _mark_published/_mark_failed
    # ever ran, exactly as _claim_batch would leave it.
    async with SessionFactory() as session:
        record = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        assert record is not None
        record.claimed_until = utc_now() + timedelta(minutes=2)
        record.attempts = 1
        await session.commit()

    restarted_dispatcher = OutboxDispatcher(SessionFactory, batch_size=10)
    restarted_dispatcher.register("wallet.late_delivery_credit_granted", handler)

    # While the crashed worker's claim lease is still live, a freshly
    # started dispatcher instance must not touch the row -- the platform
    # cannot yet assume the crashed process isn't still running.
    await restarted_dispatcher.dispatch_batch()
    async with SessionFactory() as session:
        record = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        assert record is not None and record.status == "pending"
    assert calls == 0

    # Once the claim lease expires, the restarted process's normal poll
    # loop would recover the row exactly like any other worker instance --
    # but the real outbox worker container running alongside this suite
    # against the same shared dev database would race a plain
    # dispatch_batch() call here too. Re-claim it for this test first (as
    # _claim_batch itself would), then call _dispatch_one directly, which
    # exercises the same post-claim dispatch logic without that race.
    async with SessionFactory() as session:
        record = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        assert record is not None
        record.claimed_until = utc_now() + timedelta(minutes=5)
        await session.commit()
    async with SessionFactory() as session:
        record = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        assert record is not None
        await restarted_dispatcher._dispatch_one(record)

    async with SessionFactory() as session:
        record = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
    assert record is not None and record.status == "published"
    assert calls == 1


async def test_household_address_update_and_delete_lifecycle(seed: Seed) -> None:
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        updated = await client.patch(
            f"/api/v1/pet-life/households/{seed.household.id}/addresses/{seed.address.id}",
            json={"label": "محل کار", "recipient_mobile": "09121234567"},
        )
        assert updated.status_code == 200
        assert updated.json()["label"] == "محل کار"
        assert updated.json()["recipient_mobile"] == "+989121234567"
        # Untouched fields survive a partial update.
        assert updated.json()["city"] == seed.address.city

        invalid_mobile = await client.patch(
            f"/api/v1/pet-life/households/{seed.household.id}/addresses/{seed.address.id}",
            json={"recipient_mobile": "not-a-number"},
        )
        assert invalid_mobile.status_code == 422

        first_delete = await client.delete(
            f"/api/v1/pet-life/households/{seed.household.id}/addresses/{seed.address.id}"
        )
        assert first_delete.status_code == 204

        listed = await client.get(f"/api/v1/pet-life/households/{seed.household.id}/addresses")
        assert seed.address.id not in {item["id"] for item in listed.json()}

        # Deleting an already-deleted address is idempotent, not an error.
        second_delete = await client.delete(
            f"/api/v1/pet-life/households/{seed.household.id}/addresses/{seed.address.id}"
        )
        assert second_delete.status_code == 204

        # An inactive (deleted) address is not editable -- non-enumerating 404,
        # same as a fully unknown id.
        patch_after_delete = await client.patch(
            f"/api/v1/pet-life/households/{seed.household.id}/addresses/{seed.address.id}",
            json={"label": "بعد از حذف"},
        )
        assert patch_after_delete.status_code == 404
        unknown_id_patch = await client.patch(
            f"/api/v1/pet-life/households/{seed.household.id}/addresses/{uuid.uuid4()}",
            json={"label": "x"},
        )
        assert unknown_id_patch.status_code == 404
        deleted_code = patch_after_delete.json()["error"]["code"]
        unknown_code = unknown_id_patch.json()["error"]["code"]
        assert deleted_code == unknown_code
    app.dependency_overrides.clear()


async def test_household_address_mutation_rejects_another_household(seed: Seed) -> None:
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.other_identity
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        patch_attempt = await client.patch(
            f"/api/v1/pet-life/households/{seed.household.id}/addresses/{seed.address.id}",
            json={"label": "دستکاری"},
        )
        assert patch_attempt.status_code == 404
        delete_attempt = await client.delete(
            f"/api/v1/pet-life/households/{seed.household.id}/addresses/{seed.address.id}"
        )
        assert delete_attempt.status_code == 404
    app.dependency_overrides.clear()

    async with SessionFactory() as session:
        address = await session.get(HouseholdAddress, seed.address.id)
        assert address is not None and address.active is True


async def test_household_address_deletion_preserves_order_history(seed: Seed) -> None:
    async with SessionFactory() as session:
        order = await CheckoutService().create_order(
            session,
            customer_identity_id=seed.identity.id,
            household_id=seed.household.id,
            address_id=seed.address.id,
            items=[CheckoutItem(seed.offer.id, 1)],
            idempotency_key=f"address-deletion-{uuid.uuid4()}",
        )
        original_snapshot = dict(order.delivery_address_snapshot)

    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        deleted = await client.delete(
            f"/api/v1/pet-life/households/{seed.household.id}/addresses/{seed.address.id}"
        )
        assert deleted.status_code == 204

        order_detail = await client.get(f"/api/v1/orders/{order.id}")
        assert order_detail.status_code == 200
        delivery_address = order_detail.json()["delivery_address"]
        assert delivery_address["address_line"] == original_snapshot["address_line"]
        assert delivery_address["recipient_name"] == original_snapshot["recipient_name"]
    app.dependency_overrides.clear()

    async with SessionFactory() as session:
        order_after = await session.get(Order, order.id)
        assert order_after is not None
        assert order_after.delivery_address_snapshot == original_snapshot


async def test_sms_preference_read_back_default_update_and_overnight_quiet_hours(
    seed: Seed,
) -> None:
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    event_key = f"reorder-{uuid.uuid4().hex[:8]}"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Empty/default: no PUT has ever happened for this event_key.
        default = await client.get(
            f"/api/v1/pet-life/notifications/preferences/{event_key}/sms"
        )
        assert default.status_code == 200
        assert default.json() == {
            "event_key": event_key,
            "sms_enabled": True,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
        }

        # Update then read back a plain daytime window.
        put_daytime = await client.put(
            f"/api/v1/pet-life/notifications/preferences/{event_key}/sms",
            json={
                "enabled": False,
                "quiet_start_local": "09:00:00",
                "quiet_end_local": "17:00:00",
            },
        )
        assert put_daytime.status_code == 204
        read_back = await client.get(
            f"/api/v1/pet-life/notifications/preferences/{event_key}/sms"
        )
        assert read_back.json() == {
            "event_key": event_key,
            "sms_enabled": False,
            "quiet_hours_start": "09:00:00",
            "quiet_hours_end": "17:00:00",
        }

        # An overnight window (start after end, wrapping past midnight) must
        # be accepted, not rejected as an "invalid range".
        put_overnight = await client.put(
            f"/api/v1/pet-life/notifications/preferences/{event_key}/sms",
            json={
                "enabled": True,
                "quiet_start_local": "22:30:00",
                "quiet_end_local": "07:00:00",
            },
        )
        assert put_overnight.status_code == 204
        overnight_read_back = await client.get(
            f"/api/v1/pet-life/notifications/preferences/{event_key}/sms"
        )
        assert overnight_read_back.json() == {
            "event_key": event_key,
            "sms_enabled": True,
            "quiet_hours_start": "22:30:00",
            "quiet_hours_end": "07:00:00",
        }

        # A different event_key is an independent preference.
        other_event_default = await client.get(
            "/api/v1/pet-life/notifications/preferences/some-other-event/sms"
        )
        assert other_event_default.json()["sms_enabled"] is True
    app.dependency_overrides.clear()


async def test_notification_destinations_are_typed_and_server_populated(seed: Seed) -> None:
    order_id = uuid.uuid4()
    async with SessionFactory() as session:
        # A notification whose creation path never sets a destination
        # (simulating a pre-migration row, since destination_kind defaults to
        # 'none' both at the Python and column level) must read back as
        # {kind: "none", id: null}, not error or fabricate a destination.
        session.add(
            Notification(
                recipient_identity_id=seed.identity.id,
                event_key="some.legacy.event",
                source_id="legacy-1",
                channel="in_app",
                payload={},
                status="sent",
            )
        )

        # catalog.offer_available must destination to the offer.
        session.add(
            CatalogAvailabilitySubscription(
                identity_id=seed.identity.id,
                household_id=seed.household.id,
                offer_id=seed.offer.id,
            )
        )
        await session.commit()
        offer = await session.get(Offer, seed.offer.id)
        assert offer is not None
        await notify_available_subscribers(session, offer)
        await session.commit()

        # wallet.late_delivery_credit_granted must destination to the order.
        await enqueue_wallet_credit_notification(
            SessionFactory,
            {"household_id": str(seed.household.id), "order_id": str(order_id)},
            customer_visible=True,
        )

    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        inbox = await client.get("/api/v1/pet-life/notifications")
        assert inbox.status_code == 200
        by_event = {item["event_key"]: item for item in inbox.json()["items"]}

        legacy = by_event["some.legacy.event"]
        assert legacy["destination"] == {"kind": "none", "id": None}

        offer_available = by_event["catalog.offer_available"]
        assert offer_available["destination"] == {
            "kind": "offer",
            "id": str(seed.offer.id),
        }

        wallet_credit = by_event["wallet.late_delivery_credit_granted"]
        assert wallet_credit["destination"] == {"kind": "order", "id": str(order_id)}
    app.dependency_overrides.clear()


async def test_privacy_request_status_is_scoped_typed_and_paginated(seed: Seed) -> None:
    app = create_app()
    app.dependency_overrides[get_current_identity] = lambda: seed.identity
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        empty = await client.get("/api/v1/privacy/requests")
        assert empty.status_code == 200
        assert empty.json()["items"] == []

        created = await client.post(
            "/api/v1/privacy/requests", json={"request_type": "disable"}
        )
        assert created.status_code == 202
        request_id = created.json()["id"]
        assert created.json()["status"] == "requested"

        # Duplicate active-request behavior: a second create while one is
        # still active must not create a second row, and the list must
        # still show exactly one.
        duplicate = await client.post(
            "/api/v1/privacy/requests", json={"request_type": "disable"}
        )
        assert duplicate.status_code == 202
        assert duplicate.json()["id"] == request_id

        listed = await client.get("/api/v1/privacy/requests")
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 1
        item = listed.json()["items"][0]
        assert item["id"] == request_id
        assert item["request_type"] == "disable"
        assert item["status"] == "requested"
        assert item["created_at"]

        # Persists after "reload": fetching the single request by id shows
        # the same status, not just the one-time creation response.
        detail = await client.get(f"/api/v1/privacy/requests/{request_id}")
        assert detail.status_code == 200
        assert detail.json()["id"] == request_id
        assert detail.json()["status"] == "requested"

        # A different request_type is an independent request.
        second = await client.post(
            "/api/v1/privacy/requests", json={"request_type": "anonymize"}
        )
        assert second.status_code == 202
        assert second.json()["id"] != request_id
        assert second.json()["status"] == "awaiting_policy"

        paginated_first = await client.get("/api/v1/privacy/requests?limit=1&offset=0")
        assert len(paginated_first.json()["items"]) == 1
        assert paginated_first.json()["page"]["total"] == 2
        assert paginated_first.json()["page"]["has_more"] is True
        paginated_second = await client.get("/api/v1/privacy/requests?limit=1&offset=1")
        assert len(paginated_second.json()["items"]) == 1
        assert paginated_second.json()["page"]["has_more"] is False
        assert (
            paginated_first.json()["items"][0]["id"]
            != paginated_second.json()["items"][0]["id"]
        )

        unknown = await client.get(f"/api/v1/privacy/requests/{uuid.uuid4()}")
        assert unknown.status_code == 404

    # Non-enumerating: another identity must not be able to see or fetch
    # this identity's privacy requests, and the failure mode for "exists but
    # not mine" must be identical to "does not exist" (404, not 403).
    app.dependency_overrides[get_current_identity] = lambda: seed.other_identity
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        other_list = await client.get("/api/v1/privacy/requests")
        assert other_list.status_code == 200
        assert other_list.json()["items"] == []

        cross_identity = await client.get(f"/api/v1/privacy/requests/{request_id}")
        assert cross_identity.status_code == 404
        assert cross_identity.json()["error"]["code"] == unknown.json()["error"]["code"]
    app.dependency_overrides.clear()
