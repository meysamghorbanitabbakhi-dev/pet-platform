from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from app.common.time import utc_now
from app.db.session import SessionFactory, close_database
from app.integrations.payment.port import (
    PaymentInitiation,
    PaymentInquiry,
    PaymentRequest,
    PaymentReversal,
    PaymentVerification,
)
from app.modules.catalog.models import Offer, Product, Supplier
from app.modules.checkout.service import CheckoutItem, CheckoutService
from app.modules.households.models import Household, HouseholdAddress
from app.modules.identity.models import AuthIdentity
from app.modules.orders.models import Order, OrderLine
from app.modules.payments.service import PaymentService
from app.modules.purchasing.models import PurchaseBatch, PurchaseBatchAllocation, PurchaseBatchEvent
from app.modules.purchasing.service import (
    PurchasingError,
    allocate_order_line_to_batch,
    commit_batch,
    is_order_cancellation_eligible,
)
from app.modules.trust.files import EvidenceFile
from sqlalchemy import func, select

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL is required",
)


@pytest.fixture(autouse=True)
async def dispose_engine_between_event_loops() -> AsyncIterator[None]:
    yield
    await close_database()


@dataclass(slots=True)
class OfferSeed:
    token: str
    offer_id: uuid.UUID
    order_id: uuid.UUID


async def _seed_offer(
    *, sourcing_route: str = "aggregated", default_batch_threshold_quantity: int | None = None
) -> OfferSeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        supplier = Supplier(internal_name=f"batch-supplier-{token}", country_code="IR", active=True)
        product = Product(name_fa=f"محصول دسته‌ای {token}", status="active")
        session.add_all([supplier, product])
        await session.flush()
        offer = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"BATCH-{token}",
            title_fa=f"پیشنهاد دسته‌ای {token}",
            unit_label_fa="کیسه",
            price_irr=1_000_000,
            status="active",
            stock_posture="sourced_after_payment",
            sourcing_capacity_status="open",
            minimum_shelf_life_months=6,
            sourcing_route=sourcing_route,
            default_batch_threshold_quantity=default_batch_threshold_quantity,
        )
        identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98919{token[:7]}", status="active"
        )
        session.add_all([offer, identity])
        await session.flush()
        from app.modules.households.models import Household

        household = Household(name=f"hh-batch-{token}")
        session.add(household)
        await session.flush()
        order = Order(
            customer_identity_id=identity.id,
            household_id=household.id,
            status="paid",
            currency="IRR",
            merchandise_total_irr=1_000_000,
            checkout_idempotency_key=f"batch-{token}",
            paid_at=utc_now(),
            delivery_commitment_at=utc_now(),
            delivery_address_snapshot={
                "label": "x",
                "recipient_name": "x",
                "recipient_mobile_e164": "+989120000000",
                "province": "x",
                "city": "x",
                "address_line": "x",
            },
        )
        session.add(order)
        await session.commit()
        return OfferSeed(token=token, offer_id=offer.id, order_id=order.id)


async def _add_line(seed: OfferSeed, *, quantity: int) -> OrderLine:
    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        line = OrderLine(
            order_id=seed.order_id,
            offer_id=offer.id,
            sku_snapshot=offer.sku,
            title_fa_snapshot=offer.title_fa,
            unit_label_fa_snapshot=offer.unit_label_fa,
            supplier_country_snapshot="IR",
            quantity=quantity,
            unit_price_irr=offer.price_irr,
            line_total_irr=offer.price_irr * quantity,
            created_at=utc_now(),
        )
        session.add(line)
        await session.commit()
        return line


async def test_individual_route_never_pools_two_lines_into_one_batch() -> None:
    seed = await _seed_offer(sourcing_route="individual")
    line_a = await _add_line(seed, quantity=1)
    line_b = await _add_line(seed, quantity=1)

    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        alloc_a = await allocate_order_line_to_batch(session, order_line=line_a, offer=offer)
        alloc_b = await allocate_order_line_to_batch(session, order_line=line_b, offer=offer)
        await session.commit()

    assert alloc_a.purchase_batch_id != alloc_b.purchase_batch_id
    async with SessionFactory() as session:
        batch_a = await session.get(PurchaseBatch, alloc_a.purchase_batch_id)
        batch_b = await session.get(PurchaseBatch, alloc_b.purchase_batch_id)
    assert batch_a is not None and batch_a.grouping_mode == "individual"
    assert batch_b is not None and batch_b.grouping_mode == "individual"


async def test_aggregated_route_pools_multiple_lines_into_the_same_batch() -> None:
    seed = await _seed_offer(sourcing_route="aggregated", default_batch_threshold_quantity=100)
    line_a = await _add_line(seed, quantity=3)
    line_b = await _add_line(seed, quantity=4)

    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        alloc_a = await allocate_order_line_to_batch(session, order_line=line_a, offer=offer)
        await session.commit()
    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        alloc_b = await allocate_order_line_to_batch(session, order_line=line_b, offer=offer)
        await session.commit()

    assert alloc_a.purchase_batch_id == alloc_b.purchase_batch_id
    async with SessionFactory() as session:
        batch = await session.get(PurchaseBatch, alloc_a.purchase_batch_id)
    assert batch is not None
    assert batch.allocated_quantity == 7
    assert batch.grouping_mode == "aggregated"


async def test_allocation_is_idempotent_on_replay() -> None:
    seed = await _seed_offer()
    line = await _add_line(seed, quantity=2)

    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        first = await allocate_order_line_to_batch(session, order_line=line, offer=offer)
        await session.commit()
    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        second = await allocate_order_line_to_batch(session, order_line=line, offer=offer)
        await session.commit()

    assert first.id == second.id
    async with SessionFactory() as session:
        count = (
            await session.execute(
                select(func.count(PurchaseBatchAllocation.id)).where(
                    PurchaseBatchAllocation.order_line_id == line.id
                )
            )
        ).scalar_one()
        batch = await session.get(PurchaseBatch, first.purchase_batch_id)
    assert count == 1
    assert batch is not None and batch.allocated_quantity == 2  # not double-counted


async def test_threshold_reached_is_recorded_exactly_once_when_crossed() -> None:
    seed = await _seed_offer(default_batch_threshold_quantity=5)
    line_a = await _add_line(seed, quantity=3)
    line_b = await _add_line(seed, quantity=3)  # crosses 5 on this allocation

    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        alloc_a = await allocate_order_line_to_batch(session, order_line=line_a, offer=offer)
        await session.commit()
    async with SessionFactory() as session:
        batch = await session.get(PurchaseBatch, alloc_a.purchase_batch_id)
    assert batch is not None and batch.threshold_reached_at is None

    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        await allocate_order_line_to_batch(session, order_line=line_b, offer=offer)
        await session.commit()

    async with SessionFactory() as session:
        batch = await session.get(PurchaseBatch, alloc_a.purchase_batch_id)
        event_count = (
            await session.execute(
                select(func.count(PurchaseBatchEvent.id)).where(
                    PurchaseBatchEvent.purchase_batch_id == batch.id,
                    PurchaseBatchEvent.event_type == "threshold_reached",
                )
            )
        ).scalar_one()
    assert batch is not None and batch.threshold_reached_at is not None
    assert event_count == 1


async def test_no_configured_threshold_falls_back_to_one_not_a_guessed_number() -> None:
    seed = await _seed_offer(default_batch_threshold_quantity=None)
    line = await _add_line(seed, quantity=1)

    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        allocation = await allocate_order_line_to_batch(session, order_line=line, offer=offer)
        await session.commit()

    async with SessionFactory() as session:
        batch = await session.get(PurchaseBatch, allocation.purchase_batch_id)
    assert batch is not None
    assert batch.minimum_viable_threshold_quantity == 1
    assert batch.threshold_reached_at is not None


async def test_concurrent_allocation_opens_exactly_one_aggregated_batch() -> None:
    seed = await _seed_offer(default_batch_threshold_quantity=1000)
    lines = [await _add_line(seed, quantity=2) for _ in range(10)]

    async def _allocate(line: OrderLine) -> uuid.UUID:
        async with SessionFactory() as session:
            offer = await session.get(Offer, seed.offer_id)
            assert offer is not None
            allocation = await allocate_order_line_to_batch(session, order_line=line, offer=offer)
            await session.commit()
            return allocation.purchase_batch_id

    batch_ids = await asyncio.gather(*(_allocate(line) for line in lines))
    assert len(set(batch_ids)) == 1  # every concurrent allocation landed in the same batch

    async with SessionFactory() as session:
        batch_count = (
            await session.execute(
                select(func.count(PurchaseBatch.id)).where(PurchaseBatch.offer_id == seed.offer_id)
            )
        ).scalar_one()
        batch = await session.get(PurchaseBatch, batch_ids[0])
    assert batch_count == 1  # the race never produced a second batch
    assert batch is not None and batch.allocated_quantity == 20  # no lost updates


async def test_commit_batch_is_idempotent_and_records_one_audit_event() -> None:
    seed = await _seed_offer()
    line = await _add_line(seed, quantity=1)
    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        allocation = await allocate_order_line_to_batch(session, order_line=line, offer=offer)
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98920{seed.token[:7]}", status="active"
        )
        session.add(operator)
        await session.flush()
        evidence = EvidenceFile(
            storage_key=f"evidence/{seed.token}.pdf",
            original_filename="commitment.pdf",
            media_type="application/pdf",
            size_bytes=10,
            checksum_sha256="a" * 64,
            uploaded_by_operator_id=operator.id,
        )
        session.add(evidence)
        await session.commit()
        batch_id, operator_id, evidence_id = allocation.purchase_batch_id, operator.id, evidence.id

    async with SessionFactory() as session:
        batch = await session.get(PurchaseBatch, batch_id)
        assert batch is not None
        first = await commit_batch(
            session,
            batch=batch,
            operator_id=operator_id,
            evidence_file_id=evidence_id,
            commitment_reference="PO-1234",
            reason="supplier invoice paid",
        )
        await session.commit()
    assert first.status == "committed"
    assert first.committed_at is not None

    async with SessionFactory() as session:
        batch = await session.get(PurchaseBatch, batch_id)
        assert batch is not None
        second = await commit_batch(
            session,
            batch=batch,
            operator_id=operator_id,
            evidence_file_id=evidence_id,
            commitment_reference="PO-1234",
            reason="replay",
        )
        await session.commit()
    assert second.committed_at == first.committed_at

    async with SessionFactory() as session:
        event_count = (
            await session.execute(
                select(func.count(PurchaseBatchEvent.id)).where(
                    PurchaseBatchEvent.purchase_batch_id == batch_id,
                    PurchaseBatchEvent.event_type == "committed",
                )
            )
        ).scalar_one()
    assert event_count == 1


async def test_commit_batch_rejects_a_cancelled_batch() -> None:
    seed = await _seed_offer()
    line = await _add_line(seed, quantity=1)
    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        allocation = await allocate_order_line_to_batch(session, order_line=line, offer=offer)
        await session.commit()
        batch_id = allocation.purchase_batch_id

    async with SessionFactory() as session:
        batch = await session.get(PurchaseBatch, batch_id)
        assert batch is not None
        batch.status = "cancelled"
        await session.commit()

    async with SessionFactory() as session:
        batch = await session.get(PurchaseBatch, batch_id)
        assert batch is not None
        with pytest.raises(PurchasingError):
            await commit_batch(
                session,
                batch=batch,
                operator_id=uuid.uuid4(),
                evidence_file_id=uuid.uuid4(),
                commitment_reference=None,
                reason="should be rejected",
            )


async def test_order_cancellation_eligibility_flips_once_any_line_is_committed() -> None:
    seed = await _seed_offer()
    line_a = await _add_line(seed, quantity=1)
    line_b = await _add_line(seed, quantity=1)

    async with SessionFactory() as session:
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        alloc_a = await allocate_order_line_to_batch(session, order_line=line_a, offer=offer)
        await allocate_order_line_to_batch(session, order_line=line_b, offer=offer)
        await session.commit()

    async with SessionFactory() as session:
        eligible = await is_order_cancellation_eligible(session, order_id=seed.order_id)
    assert eligible is True

    async with SessionFactory() as session:
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98921{seed.token[:7]}", status="active"
        )
        session.add(operator)
        await session.flush()
        evidence = EvidenceFile(
            storage_key=f"evidence/{seed.token}-b.pdf",
            original_filename="commitment.pdf",
            media_type="application/pdf",
            size_bytes=10,
            checksum_sha256="b" * 64,
            uploaded_by_operator_id=operator.id,
        )
        session.add(evidence)
        await session.flush()
        batch = await session.get(PurchaseBatch, alloc_a.purchase_batch_id)
        assert batch is not None
        await commit_batch(
            session,
            batch=batch,
            operator_id=operator.id,
            evidence_file_id=evidence.id,
            commitment_reference=None,
            reason="committed one of two lines",
        )
        await session.commit()

    async with SessionFactory() as session:
        eligible = await is_order_cancellation_eligible(session, order_id=seed.order_id)
    assert eligible is False  # even one committed line blocks the whole order


class _FakePaymentGateway:
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


async def test_real_checkout_and_payment_verify_allocates_the_order_line_to_a_batch() -> None:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        identity = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98922{token[:7]}", status="active"
        )
        household = Household(name=f"hh-e2e-batch-{token}")
        session.add_all([identity, household])
        await session.flush()
        address = HouseholdAddress(
            household_id=household.id,
            label="خانه",
            recipient_name="مالک خانه",
            recipient_mobile_e164="+989120000000",
            province="تهران",
            city="تهران",
            address_line="خیابان ولیعصر",
            active=True,
        )
        supplier = Supplier(internal_name=f"e2e-supplier-{token}", country_code="IR", active=True)
        product = Product(name_fa=f"محصول e2e {token}", status="active")
        session.add_all([address, supplier, product])
        await session.flush()
        offer = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"E2E-{token}",
            title_fa=f"پیشنهاد e2e {token}",
            unit_label_fa="کیسه",
            price_irr=2_000_000,
            status="active",
            stock_posture="sourced_after_payment",
            sourcing_capacity_status="open",
            minimum_shelf_life_months=6,
            sourcing_route="aggregated",
        )
        session.add(offer)
        await session.commit()
        identity_id, household_id, address_id, offer_id = (
            identity.id,
            household.id,
            address.id,
            offer.id,
        )

    gateway = _FakePaymentGateway()
    async with SessionFactory() as session:
        order = await CheckoutService().create_order(
            session,
            customer_identity_id=identity_id,
            household_id=household_id,
            address_id=address_id,
            items=[CheckoutItem(offer_id, 2)],
            idempotency_key=f"e2e-checkout-{token}",
        )
    async with SessionFactory() as session:
        await PaymentService().initiate(
            session,
            gateway,
            order_id=order.id,
            customer_identity_id=identity_id,
            customer_mobile_e164="+989220000000",
            callback_url="https://app.test/callback",
            idempotency_key=f"e2e-payment-{token}",
        )
    async with SessionFactory() as session:
        await PaymentService().verify(
            session, gateway, provider_reference=f"fake-{order.id}"
        )

    async with SessionFactory() as session:
        line = await session.scalar(select(OrderLine).where(OrderLine.order_id == order.id))
        assert line is not None
        allocation = await session.scalar(
            select(PurchaseBatchAllocation).where(
                PurchaseBatchAllocation.order_line_id == line.id
            )
        )
        assert allocation is not None
        batch = await session.get(PurchaseBatch, allocation.purchase_batch_id)
    assert batch is not None
    assert batch.offer_id == offer_id
    assert batch.allocated_quantity == 2
    assert batch.status == "open"
