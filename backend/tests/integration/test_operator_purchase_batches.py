from __future__ import annotations

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
from app.modules.orders.models import Order, OrderLine
from app.modules.purchasing.models import PurchaseBatch
from app.modules.purchasing.service import allocate_order_line_to_batch
from app.modules.system.models import OperatorAuditLog
from app.modules.trust.files import EvidenceFile
from fastapi import FastAPI
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
class BatchSeed:
    operator: AuthIdentity
    customer: AuthIdentity
    offer_id: str
    order_line_id: str


@pytest.fixture()
async def batch_seed() -> BatchSeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98913{token[:7]}", status="active"
        )
        customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98914{token[:7]}", status="active"
        )
        supplier = Supplier(
            internal_name=f"batch-supplier-{token}", country_code="IR", active=True
        )
        product = Product(name_fa=f"محصول {token}", status="active")
        household = Household(name=f"خانواده {token}")
        session.add_all([operator, customer, supplier, product, household])
        await session.flush()
        offer = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"BATCH-{token}",
            title_fa=f"پیشنهاد {token}",
            unit_label_fa="کیسه",
            price_irr=1_000_000,
            status="active",
            stock_posture="sourced_after_payment",
            sourcing_capacity_status="open",
            minimum_shelf_life_months=6,
            sourcing_route="aggregated",
            default_batch_threshold_quantity=10,
        )
        session.add(offer)
        await session.flush()
        order = Order(
            customer_identity_id=customer.id,
            household_id=household.id,
            status="paid",
            currency="IRR",
            merchandise_total_irr=4_000_000,
            checkout_idempotency_key=f"batch-checkout-{token}",
            delivery_address_snapshot={"line": "test address"},
        )
        session.add(order)
        await session.flush()
        order_line = OrderLine(
            order_id=order.id,
            offer_id=offer.id,
            sku_snapshot=offer.sku,
            title_fa_snapshot=offer.title_fa,
            unit_label_fa_snapshot=offer.unit_label_fa,
            supplier_country_snapshot=supplier.country_code,
            quantity=4,
            unit_price_irr=offer.price_irr,
            line_total_irr=offer.price_irr * 4,
            created_at=utc_now(),
        )
        session.add(order_line)
        await session.commit()
        return BatchSeed(
            operator=operator,
            customer=customer,
            offer_id=str(offer.id),
            order_line_id=str(order_line.id),
        )


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def _audit_count(action: str, resource_id: str) -> int:
    async with SessionFactory() as session:
        return (
            await session.execute(
                select(func.count(OperatorAuditLog.id)).where(
                    OperatorAuditLog.action == action,
                    OperatorAuditLog.resource_id == resource_id,
                )
            )
        ).scalar_one()


async def _open_batch(seed: BatchSeed) -> str:
    """Create an open batch the same way payment verification does, without
    going through HTTP -- these tests exercise the operator management
    surface over an already-existing batch, not batch creation itself
    (covered end-to-end in test_purchasing_batches.py)."""
    async with SessionFactory() as session:
        offer = await session.get(Offer, uuid.UUID(seed.offer_id))
        order_line = await session.get(OrderLine, uuid.UUID(seed.order_line_id))
        assert offer is not None
        assert order_line is not None
        allocation = await allocate_order_line_to_batch(
            session, order_line=order_line, offer=offer
        )
        await session.commit()
        return str(allocation.purchase_batch_id)


async def _evidence_file(operator_id: uuid.UUID) -> str:
    async with SessionFactory() as session:
        evidence = EvidenceFile(
            storage_key=f"evidence/{uuid.uuid4()}/commitment.pdf",
            original_filename="commitment.pdf",
            media_type="application/pdf",
            size_bytes=128,
            checksum_sha256="0" * 64,
            uploaded_by_operator_id=operator_id,
        )
        session.add(evidence)
        await session.commit()
        return str(evidence.id)


async def test_sourcing_config_update_changes_route_and_threshold(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator

    response = await client.patch(
        f"/api/v1/operator/offers/{batch_seed.offer_id}/sourcing-config",
        json={
            "sourcing_route": "individual",
            "default_batch_threshold_quantity": None,
            "reason": "exceptional supplier requires per-order sourcing",
        },
    )
    assert response.status_code == 204

    async with SessionFactory() as session:
        offer = await session.get(Offer, uuid.UUID(batch_seed.offer_id))
        assert offer is not None
        assert offer.sourcing_route == "individual"
        assert offer.default_batch_threshold_quantity is None
    assert await _audit_count("offer.sourcing_config_updated", batch_seed.offer_id) == 1


async def test_sourcing_config_rejects_invalid_route(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator

    response = await client.patch(
        f"/api/v1/operator/offers/{batch_seed.offer_id}/sourcing-config",
        json={"sourcing_route": "bulk", "reason": "invalid route value"},
    )
    assert response.status_code == 422


async def test_sourcing_config_rejects_aggregated_route_without_a_threshold(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator

    response = await client.patch(
        f"/api/v1/operator/offers/{batch_seed.offer_id}/sourcing-config",
        json={
            "sourcing_route": "aggregated",
            "default_batch_threshold_quantity": None,
            "reason": "switching back to pooled sourcing",
        },
    )
    assert response.status_code == 422
    assert (
        response.json()["error"]["code"]
        == "aggregated_route_requires_default_batch_threshold_quantity"
    )

    async with SessionFactory() as session:
        offer = await session.get(Offer, uuid.UUID(batch_seed.offer_id))
        assert offer is not None
        assert offer.sourcing_route == "aggregated"
        assert offer.default_batch_threshold_quantity == 10


async def test_list_and_detail_reflect_allocation_state(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator
    batch_id = await _open_batch(batch_seed)

    listed = await client.get(
        "/api/v1/operator/purchase-batches", params={"offer_id": batch_seed.offer_id}
    )
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["id"] == batch_id
    assert items[0]["status"] == "open"
    assert items[0]["allocated_quantity"] == 4
    assert items[0]["minimum_viable_threshold_quantity"] == 10
    assert items[0]["threshold_reached_at"] is None

    detail = await client.get(f"/api/v1/operator/purchase-batches/{batch_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == batch_id
    assert len(body["allocations"]) == 1
    assert body["allocations"][0]["order_line_id"] == batch_seed.order_line_id
    assert body["allocations"][0]["quantity"] == 4
    assert [event["event_type"] for event in body["events"]] == ["opened"]


async def test_list_rejects_invalid_status_filter(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator

    response = await client.get(
        "/api/v1/operator/purchase-batches", params={"status": "not_a_real_status"}
    )
    assert response.status_code == 422


async def test_detail_unknown_batch_is_404(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator

    response = await client.get(f"/api/v1/operator/purchase-batches/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_adjust_lowering_threshold_below_allocated_retroactively_reaches_it(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator
    batch_id = await _open_batch(batch_seed)

    response = await client.patch(
        f"/api/v1/operator/purchase-batches/{batch_id}",
        json={
            "minimum_viable_threshold_quantity": 3,
            "deadline_at": None,
            "reason": "deadline approaching, lowering threshold to source early",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["minimum_viable_threshold_quantity"] == 3
    assert body["threshold_reached_at"] is not None
    assert await _audit_count("purchase_batch.adjusted", batch_id) == 1

    detail = await client.get(f"/api/v1/operator/purchase-batches/{batch_id}")
    events = [event["event_type"] for event in detail.json()["events"]]
    assert events == ["opened", "threshold_reached"]
    threshold_event = detail.json()["events"][1]
    assert threshold_event["operator_identity_id"] == str(batch_seed.operator.id)


async def test_adjust_raising_threshold_does_not_unset_already_reached(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator
    batch_id = await _open_batch(batch_seed)

    first = await client.patch(
        f"/api/v1/operator/purchase-batches/{batch_id}",
        json={
            "minimum_viable_threshold_quantity": 2,
            "reason": "lower threshold to trigger early sourcing",
        },
    )
    assert first.json()["threshold_reached_at"] is not None
    reached_at = first.json()["threshold_reached_at"]

    second = await client.patch(
        f"/api/v1/operator/purchase-batches/{batch_id}",
        json={
            "minimum_viable_threshold_quantity": 50,
            "reason": "raise threshold back up, should not erase history",
        },
    )
    assert second.status_code == 200
    assert second.json()["threshold_reached_at"] == reached_at


async def test_adjust_is_blocked_once_committed(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator
    batch_id = await _open_batch(batch_seed)
    evidence_id = await _evidence_file(batch_seed.operator.id)

    committed = await client.post(
        f"/api/v1/operator/purchase-batches/{batch_id}/commit",
        json={"evidence_file_id": evidence_id, "reason": "supplier invoice paid"},
    )
    assert committed.status_code == 200
    assert committed.json()["status"] == "committed"

    blocked = await client.patch(
        f"/api/v1/operator/purchase-batches/{batch_id}",
        json={"minimum_viable_threshold_quantity": 1, "reason": "should be rejected"},
    )
    assert blocked.status_code == 409


async def test_commit_is_idempotent_and_audits_once(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator
    batch_id = await _open_batch(batch_seed)
    evidence_id = await _evidence_file(batch_seed.operator.id)

    first = await client.post(
        f"/api/v1/operator/purchase-batches/{batch_id}/commit",
        json={
            "evidence_file_id": evidence_id,
            "commitment_reference": "INV-0042",
            "reason": "supplier invoice paid in full",
        },
    )
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "committed"
    assert body["committed_by_operator_id"] == str(batch_seed.operator.id)
    assert body["commitment_evidence_file_id"] == evidence_id
    assert body["commitment_reference"] == "INV-0042"
    assert await _audit_count("purchase_batch.committed", batch_id) == 1

    replay = await client.post(
        f"/api/v1/operator/purchase-batches/{batch_id}/commit",
        json={"evidence_file_id": evidence_id, "reason": "retry after client timeout"},
    )
    assert replay.status_code == 200
    assert replay.json()["status"] == "committed"
    assert await _audit_count("purchase_batch.committed", batch_id) == 1


async def test_commit_unknown_evidence_file_is_404(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator
    batch_id = await _open_batch(batch_seed)

    response = await client.post(
        f"/api/v1/operator/purchase-batches/{batch_id}/commit",
        json={"evidence_file_id": str(uuid.uuid4()), "reason": "evidence does not exist"},
    )
    assert response.status_code == 404


async def test_commit_unknown_batch_is_404(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator
    evidence_id = await _evidence_file(batch_seed.operator.id)

    response = await client.post(
        f"/api/v1/operator/purchase-batches/{uuid.uuid4()}/commit",
        json={"evidence_file_id": evidence_id, "reason": "batch does not exist"},
    )
    assert response.status_code == 404


async def _empty_batch(seed: BatchSeed) -> str:
    """An open aggregated batch with no allocations -- e.g. opened but the
    order that would have allocated into it was itself cancelled first, or
    simply never received one. Constructed directly since
    allocate_order_line_to_batch always creates an allocation alongside
    the batch."""
    async with SessionFactory() as session:
        batch = PurchaseBatch(
            offer_id=uuid.UUID(seed.offer_id),
            grouping_mode="aggregated",
            status="open",
            minimum_viable_threshold_quantity=10,
        )
        session.add(batch)
        await session.commit()
        return str(batch.id)


async def test_cancel_an_empty_batch(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator
    batch_id = await _empty_batch(batch_seed)

    response = await client.post(
        f"/api/v1/operator/purchase-batches/{batch_id}/cancel",
        json={"reason": "offer was pulled before any order pooled into it"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["cancelled_by_operator_id"] == str(batch_seed.operator.id)
    assert await _audit_count("purchase_batch.cancelled", batch_id) == 1

    replay = await client.post(
        f"/api/v1/operator/purchase-batches/{batch_id}/cancel",
        json={"reason": "retry after client timeout"},
    )
    assert replay.status_code == 200
    assert replay.json()["status"] == "cancelled"
    assert await _audit_count("purchase_batch.cancelled", batch_id) == 1


async def test_cancel_rejects_a_batch_with_active_allocations(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator
    batch_id = await _open_batch(batch_seed)

    response = await client.post(
        f"/api/v1/operator/purchase-batches/{batch_id}/cancel",
        json={"reason": "trying to cancel a batch with a live order in it"},
    )
    assert response.status_code == 409

    async with SessionFactory() as session:
        batch = await session.get(PurchaseBatch, uuid.UUID(batch_id))
        assert batch is not None
        assert batch.status == "open"


async def test_cancel_is_blocked_once_committed(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator
    batch_id = await _open_batch(batch_seed)
    evidence_id = await _evidence_file(batch_seed.operator.id)
    committed = await client.post(
        f"/api/v1/operator/purchase-batches/{batch_id}/commit",
        json={"evidence_file_id": evidence_id, "reason": "supplier invoice paid in full"},
    )
    assert committed.status_code == 200

    response = await client.post(
        f"/api/v1/operator/purchase-batches/{batch_id}/cancel",
        json={"reason": "trying to cancel an already-committed batch"},
    )
    assert response.status_code == 409


async def test_cancel_unknown_batch_is_404(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.operator

    response = await client.post(
        f"/api/v1/operator/purchase-batches/{uuid.uuid4()}/cancel",
        json={"reason": "batch does not exist"},
    )
    assert response.status_code == 404


async def test_non_operator_identity_is_forbidden(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], batch_seed: BatchSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: batch_seed.customer

    response = await client.get("/api/v1/operator/purchase-batches")
    assert response.status_code == 403

    batch_id = await _empty_batch(batch_seed)
    cancel = await client.post(
        f"/api/v1/operator/purchase-batches/{batch_id}/cancel",
        json={"reason": "a customer should never reach this"},
    )
    assert cancel.status_code == 403
