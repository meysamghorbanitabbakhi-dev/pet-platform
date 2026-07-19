from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
from app.api.dependencies import get_current_identity
from app.common.time import utc_now
from app.db.session import SessionFactory, close_database
from app.main import create_app
from app.modules.catalog.models import Offer, Product, Supplier
from app.modules.households.models import Household
from app.modules.identity.models import AuthIdentity
from app.modules.orders.cancellation import (
    CancellationError,
    OrderCancellation,
    cancel_order_by_customer,
    is_order_cancellation_eligible_now,
)
from app.modules.orders.models import Order, OrderLine
from app.modules.purchasing.models import PurchaseBatch, PurchaseBatchAllocation
from app.modules.purchasing.service import allocate_order_line_to_batch, commit_batch
from app.modules.trust.files import EvidenceFile
from sqlalchemy import select

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
    operator_id: uuid.UUID


@dataclass(slots=True)
class OrderSeed:
    order_id: uuid.UUID
    order_line_id: uuid.UUID
    customer_id: uuid.UUID
    batch_id: uuid.UUID


async def _seed_offer(
    *, default_batch_threshold_quantity: int | None = None
) -> OfferSeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        supplier = Supplier(
            internal_name=f"cancel-supplier-{token}", country_code="IR", active=True
        )
        product = Product(name_fa=f"محصول لغو {token}", status="active")
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98918{token[:7]}", status="active"
        )
        session.add_all([supplier, product, operator])
        await session.flush()
        offer = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"CANCEL-{token}",
            title_fa=f"پیشنهاد لغو {token}",
            unit_label_fa="کیسه",
            price_irr=1_000_000,
            status="active",
            stock_posture="sourced_after_payment",
            sourcing_capacity_status="open",
            minimum_shelf_life_months=6,
            sourcing_route="aggregated",
            default_batch_threshold_quantity=default_batch_threshold_quantity,
        )
        session.add(offer)
        await session.commit()
        return OfferSeed(token=token, offer_id=offer.id, operator_id=operator.id)


async def _seed_paid_order_allocated_to_batch(
    seed: OfferSeed, *, quantity: int = 2
) -> OrderSeed:
    """A paid order with one line, already allocated to seed.offer_id's
    open aggregated batch -- mirrors what PaymentService.verify() does,
    without the full checkout/payment machinery (that path is covered
    end-to-end in test_purchasing_batches.py)."""
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98919{token[:7]}", status="active"
        )
        household = Household(name=f"hh-cancel-{token}")
        session.add_all([customer, household])
        await session.flush()
        order = Order(
            customer_identity_id=customer.id,
            household_id=household.id,
            status="paid",
            currency="IRR",
            merchandise_total_irr=1_000_000 * quantity,
            checkout_idempotency_key=f"cancel-{token}",
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
        await session.flush()
        offer = await session.get(Offer, seed.offer_id)
        assert offer is not None
        line = OrderLine(
            order_id=order.id,
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
        await session.flush()
        allocation = await allocate_order_line_to_batch(session, order_line=line, offer=offer)
        await session.commit()
        return OrderSeed(
            order_id=order.id,
            order_line_id=line.id,
            customer_id=customer.id,
            batch_id=allocation.purchase_batch_id,
        )


async def _evidence_file(operator_id: uuid.UUID) -> uuid.UUID:
    async with SessionFactory() as session:
        evidence = EvidenceFile(
            storage_key=f"evidence/{uuid.uuid4()}/commitment.pdf",
            original_filename="commitment.pdf",
            media_type="application/pdf",
            size_bytes=64,
            checksum_sha256="1" * 64,
            uploaded_by_operator_id=operator_id,
        )
        session.add(evidence)
        await session.commit()
        return evidence.id


async def _commit_batch_by_id(
    batch_id: uuid.UUID, *, operator_id: uuid.UUID, evidence_id: uuid.UUID
) -> None:
    async with SessionFactory() as session:
        batch = await session.get(PurchaseBatch, batch_id, with_for_update=True)
        assert batch is not None
        await commit_batch(
            session,
            batch=batch,
            operator_id=operator_id,
            evidence_file_id=evidence_id,
            commitment_reference="PO-CANCEL-TEST",
            reason="supplier invoice paid",
        )
        await session.commit()


# --- service-level behavior ------------------------------------------------


async def test_cancel_before_commitment_succeeds_and_marks_refund_owed() -> None:
    offer_seed = await _seed_offer()
    order_seed = await _seed_paid_order_allocated_to_batch(offer_seed, quantity=3)

    async with SessionFactory() as session:
        order = await session.scalar(
            select(Order).where(Order.id == order_seed.order_id).with_for_update()
        )
        assert order is not None
        cancellation = await cancel_order_by_customer(
            session,
            order=order,
            customer_identity_id=order_seed.customer_id,
            reason="changed my mind before it shipped",
        )
        await session.commit()

    assert cancellation.refund_status == "owed"
    assert cancellation.refund_amount_irr == 3_000_000
    assert cancellation.order_snapshot["order"]["merchandise_total_irr"] == 3_000_000
    assert len(cancellation.order_snapshot["lines"]) == 1

    async with SessionFactory() as session:
        order = await session.get(Order, order_seed.order_id)
        allocation = await session.scalar(
            select(PurchaseBatchAllocation).where(
                PurchaseBatchAllocation.order_line_id == order_seed.order_line_id
            )
        )
        batch = await session.get(PurchaseBatch, order_seed.batch_id)
    assert order is not None and order.status == "cancelled"
    assert allocation is not None and allocation.voided_at is not None
    assert batch is not None and batch.allocated_quantity == 0


async def test_cancel_is_idempotent_on_replay() -> None:
    offer_seed = await _seed_offer()
    order_seed = await _seed_paid_order_allocated_to_batch(offer_seed)

    async def _cancel_once(reason: str) -> OrderCancellation:
        async with SessionFactory() as session:
            order = await session.scalar(
                select(Order).where(Order.id == order_seed.order_id).with_for_update()
            )
            assert order is not None
            cancellation = await cancel_order_by_customer(
                session, order=order, customer_identity_id=order_seed.customer_id, reason=reason
            )
            await session.commit()
            return cancellation

    first = await _cancel_once("first attempt")
    second = await _cancel_once("retry after client timeout")
    assert first.id == second.id
    assert first.reason == "first attempt"  # replay does not overwrite the original reason

    async with SessionFactory() as session:
        count = len(
            (
                await session.scalars(
                    select(OrderCancellation).where(
                        OrderCancellation.order_id == order_seed.order_id
                    )
                )
            ).all()
        )
    assert count == 1


async def test_cancel_is_rejected_once_batch_is_committed() -> None:
    offer_seed = await _seed_offer()
    order_seed = await _seed_paid_order_allocated_to_batch(offer_seed)
    evidence_id = await _evidence_file(offer_seed.operator_id)
    await _commit_batch_by_id(
        order_seed.batch_id, operator_id=offer_seed.operator_id, evidence_id=evidence_id
    )

    async with SessionFactory() as session:
        order = await session.scalar(
            select(Order).where(Order.id == order_seed.order_id).with_for_update()
        )
        assert order is not None
        with pytest.raises(CancellationError):
            await cancel_order_by_customer(
                session,
                order=order,
                customer_identity_id=order_seed.customer_id,
                reason="too late, but trying anyway",
            )
        await session.rollback()

    async with SessionFactory() as session:
        order = await session.get(Order, order_seed.order_id)
        cancellation = await session.scalar(
            select(OrderCancellation).where(OrderCancellation.order_id == order_seed.order_id)
        )
    assert order is not None and order.status == "paid"  # unchanged
    assert cancellation is None


async def test_cancel_rejects_order_not_in_a_cancellable_status() -> None:
    offer_seed = await _seed_offer()
    order_seed = await _seed_paid_order_allocated_to_batch(offer_seed)
    async with SessionFactory() as session:
        order = await session.scalar(
            select(Order).where(Order.id == order_seed.order_id).with_for_update()
        )
        assert order is not None
        order.status = "delivered"
        await session.commit()

    async with SessionFactory() as session:
        order = await session.scalar(
            select(Order).where(Order.id == order_seed.order_id).with_for_update()
        )
        assert order is not None
        with pytest.raises(CancellationError):
            await cancel_order_by_customer(
                session, order=order, customer_identity_id=order_seed.customer_id, reason="too late"
            )
        await session.rollback()


async def test_commit_after_cancellation_still_succeeds_for_other_lines_in_the_batch() -> None:
    """Aggregated batches pool multiple orders. Cancelling one customer's
    line must not block the batch from being committed for the other,
    still-active customers -- batch-level re-evaluation after a voided
    allocation is explicitly out of scope (see
    void_allocations_for_cancelled_order's docstring)."""
    offer_seed = await _seed_offer()
    cancelled_seed = await _seed_paid_order_allocated_to_batch(offer_seed, quantity=2)
    kept_seed = await _seed_paid_order_allocated_to_batch(offer_seed, quantity=5)
    assert cancelled_seed.batch_id == kept_seed.batch_id  # both pooled into the same batch

    async with SessionFactory() as session:
        order = await session.scalar(
            select(Order).where(Order.id == cancelled_seed.order_id).with_for_update()
        )
        assert order is not None
        await cancel_order_by_customer(
            session,
            order=order,
            customer_identity_id=cancelled_seed.customer_id,
            reason="no longer needed",
        )
        await session.commit()

    evidence_id = await _evidence_file(offer_seed.operator_id)
    await _commit_batch_by_id(
        kept_seed.batch_id, operator_id=offer_seed.operator_id, evidence_id=evidence_id
    )

    async with SessionFactory() as session:
        batch = await session.get(PurchaseBatch, kept_seed.batch_id)
        kept_allocation = await session.scalar(
            select(PurchaseBatchAllocation).where(
                PurchaseBatchAllocation.order_line_id == kept_seed.order_line_id
            )
        )
        cancelled_allocation = await session.scalar(
            select(PurchaseBatchAllocation).where(
                PurchaseBatchAllocation.order_line_id == cancelled_seed.order_line_id
            )
        )
    assert batch is not None and batch.status == "committed"
    assert batch.allocated_quantity == 5  # only the kept line's quantity remains
    assert kept_allocation is not None and kept_allocation.voided_at is None
    assert cancelled_allocation is not None and cancelled_allocation.voided_at is not None


async def test_eligibility_flag_reflects_batch_commitment_state() -> None:
    offer_seed = await _seed_offer()
    order_seed = await _seed_paid_order_allocated_to_batch(offer_seed)

    async with SessionFactory() as session:
        order = await session.get(Order, order_seed.order_id)
        assert order is not None
        assert await is_order_cancellation_eligible_now(session, order=order) is True

    evidence_id = await _evidence_file(offer_seed.operator_id)
    await _commit_batch_by_id(
        order_seed.batch_id, operator_id=offer_seed.operator_id, evidence_id=evidence_id
    )

    async with SessionFactory() as session:
        order = await session.get(Order, order_seed.order_id)
        assert order is not None
        assert await is_order_cancellation_eligible_now(session, order=order) is False


# --- concurrency: cancellation vs. supplier commitment ----------------------


async def _race_cancel(order_seed: OrderSeed, *, delay: float = 0.0) -> str:
    if delay:
        await asyncio.sleep(delay)
    async with SessionFactory() as session:
        order = await session.scalar(
            select(Order).where(Order.id == order_seed.order_id).with_for_update()
        )
        assert order is not None
        try:
            await cancel_order_by_customer(
                session,
                order=order,
                customer_identity_id=order_seed.customer_id,
                reason="race test",
            )
        except CancellationError:
            await session.rollback()
            return "rejected"
        await session.commit()
        return "cancelled"


async def _race_commit(
    order_seed: OrderSeed, offer_seed: OfferSeed, evidence_id: uuid.UUID, *, delay: float = 0.0
) -> str:
    if delay:
        await asyncio.sleep(delay)
    async with SessionFactory() as session:
        batch = await session.get(PurchaseBatch, order_seed.batch_id, with_for_update=True)
        assert batch is not None
        await commit_batch(
            session,
            batch=batch,
            operator_id=offer_seed.operator_id,
            evidence_file_id=evidence_id,
            commitment_reference=None,
            reason="race test",
        )
        await session.commit()
        return "committed"


async def test_concurrent_cancellation_never_wins_after_commitment_locks_the_batch() -> None:
    # cancel_order_by_customer does several preliminary queries (order
    # lookup, existing-cancellation check, allocation lookup) before it
    # ever reaches the contended PurchaseBatch row, while commit_batch's
    # caller locks that row on its very first query -- so with zero
    # handicap, commit structurally wins every single trial and the
    # "cancel wins" branch of the invariant below would never actually run.
    # Alternating a small head start forces both lock-acquisition orderings
    # to occur across trials, while both tasks still run concurrently via
    # asyncio.gather and genuinely contend for the same row in Postgres --
    # the delay only biases who arrives first, it doesn't serialize them.
    cancel_wins = 0
    commit_wins_first = 0

    for trial in range(15):
        offer_seed = await _seed_offer()
        order_seed = await _seed_paid_order_allocated_to_batch(offer_seed)
        evidence_id = await _evidence_file(offer_seed.operator_id)

        give_cancel_a_head_start = trial % 2 == 0
        cancel_result, commit_result = await asyncio.gather(
            _race_cancel(order_seed, delay=0.0 if give_cancel_a_head_start else 0.05),
            _race_commit(
                order_seed, offer_seed, evidence_id, delay=0.05 if give_cancel_a_head_start else 0.0
            ),
        )
        assert commit_result == "committed"  # commit_batch never rejects in this scenario

        async with SessionFactory() as session:
            batch = await session.get(PurchaseBatch, order_seed.batch_id)
            cancellation = await session.scalar(
                select(OrderCancellation).where(OrderCancellation.order_id == order_seed.order_id)
            )
        # commit_batch never rejects on its own in this scenario, so the
        # batch is always committed by the end of every trial regardless
        # of which side won the lock race.
        assert batch is not None and batch.committed_at is not None

        if cancel_result == "cancelled":
            cancel_wins += 1
            assert cancellation is not None
            # The required, one-directional invariant: if cancellation
            # succeeded at all, it must have observed the batch as not
            # yet committed at that moment -- which, given both
            # transactions lock the same PurchaseBatch row, is only
            # possible if cancellation's transaction committed before
            # commit_batch's. A real bug here would show cancellation
            # succeeding *after* (chronologically later than) the
            # commitment it should have seen.
            assert cancellation.created_at <= batch.committed_at, (
                "cancellation succeeded after the batch was already committed"
            )
        else:
            commit_wins_first += 1
            assert cancellation is None

    # Both lock-acquisition orderings were genuinely exercised, not just
    # one side trivially winning every time.
    assert cancel_wins > 0
    assert commit_wins_first > 0


# --- HTTP layer --------------------------------------------------------------


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[object, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def test_http_cancel_happy_path_and_replay(
    app_and_client: tuple[object, httpx.AsyncClient]
) -> None:
    app, client = app_and_client
    offer_seed = await _seed_offer()
    order_seed = await _seed_paid_order_allocated_to_batch(offer_seed, quantity=1)
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, order_seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer

    before = await client.get(f"/api/v1/orders/{order_seed.order_id}")
    assert before.status_code == 200
    assert before.json()["cancellation_eligible"] is True
    assert before.json()["cancellation"] is None

    response = await client.post(
        f"/api/v1/orders/{order_seed.order_id}/cancel",
        json={"reason": "found a better price elsewhere"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["refund_status"] == "owed"
    assert body["refund_auto_processed"] is False
    assert body["refund_amount_irr"] == 1_000_000

    replay = await client.post(
        f"/api/v1/orders/{order_seed.order_id}/cancel",
        json={"reason": "retry after client timeout"},
    )
    assert replay.status_code == 200
    assert replay.json()["cancelled_at"] == body["cancelled_at"]

    after = await client.get(f"/api/v1/orders/{order_seed.order_id}")
    assert after.status_code == 200
    after_body = after.json()
    assert after_body["status"] == "cancelled"
    assert after_body["cancellation_eligible"] is False
    assert after_body["cancellation"]["refund_status"] == "owed"


async def test_http_cancel_after_commitment_is_conflict(
    app_and_client: tuple[object, httpx.AsyncClient]
) -> None:
    app, client = app_and_client
    offer_seed = await _seed_offer()
    order_seed = await _seed_paid_order_allocated_to_batch(offer_seed)
    evidence_id = await _evidence_file(offer_seed.operator_id)
    await _commit_batch_by_id(
        order_seed.batch_id, operator_id=offer_seed.operator_id, evidence_id=evidence_id
    )
    async with SessionFactory() as session:
        customer = await session.get(AuthIdentity, order_seed.customer_id)
    app.dependency_overrides[get_current_identity] = lambda: customer

    response = await client.post(
        f"/api/v1/orders/{order_seed.order_id}/cancel",
        json={"reason": "trying anyway"},
    )
    assert response.status_code == 409

    detail = await client.get(f"/api/v1/orders/{order_seed.order_id}")
    assert detail.json()["cancellation_eligible"] is False
    assert detail.json()["cancellation"] is None


async def test_http_cancel_is_non_enumerating_for_missing_and_foreign_orders(
    app_and_client: tuple[object, httpx.AsyncClient]
) -> None:
    app, client = app_and_client
    offer_seed = await _seed_offer()
    order_seed = await _seed_paid_order_allocated_to_batch(offer_seed)
    async with SessionFactory() as session:
        other_customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98917{offer_seed.token[:7]}", status="active"
        )
        session.add(other_customer)
        await session.commit()
        other_customer_id = other_customer.id
        other_customer_obj = await session.get(AuthIdentity, other_customer_id)
    app.dependency_overrides[get_current_identity] = lambda: other_customer_obj

    nonexistent = await client.post(
        f"/api/v1/orders/{uuid.uuid4()}/cancel", json={"reason": "does not exist"}
    )
    foreign = await client.post(
        f"/api/v1/orders/{order_seed.order_id}/cancel", json={"reason": "not mine"}
    )
    assert nonexistent.status_code == foreign.status_code == 404
    assert nonexistent.json()["error"]["code"] == foreign.json()["error"]["code"]
    assert nonexistent.json()["error"]["message"] == foreign.json()["error"]["message"]
