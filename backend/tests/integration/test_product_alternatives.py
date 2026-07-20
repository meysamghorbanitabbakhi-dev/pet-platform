from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
from app.api.dependencies import get_current_identity
from app.db.session import SessionFactory, close_database
from app.main import create_app
from app.modules.catalog.models import Offer, Product, ProductAlternative, Supplier
from app.modules.identity.models import AuthIdentity
from app.modules.system.models import OperatorAuditLog
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
class AltSeed:
    token: str
    operator: AuthIdentity
    customer: AuthIdentity
    source_product_id: str
    alternative_product_id: str  # has a currently-available offer
    unavailable_alternative_product_id: str  # has no currently-available offer


@pytest.fixture()
async def alt_seed() -> AltSeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98913{token[:7]}", status="active"
        )
        customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98914{token[:7]}", status="active"
        )
        supplier = Supplier(internal_name=f"alt-supplier-{token}", country_code="IR", active=True)
        source_product = Product(name_fa=f"محصول مبدا {token}", status="active")
        alt_product = Product(name_fa=f"محصول جایگزین {token}", status="active")
        unavailable_alt_product = Product(name_fa=f"محصول ناموجود {token}", status="active")
        session.add_all(
            [operator, customer, supplier, source_product, alt_product, unavailable_alt_product]
        )
        await session.flush()
        session.add_all(
            [
                Offer(
                    product_id=alt_product.id,
                    supplier_id=supplier.id,
                    sku=f"ALT-{token}",
                    title_fa=f"پیشنهاد جایگزین {token}",
                    unit_label_fa="کیسه",
                    price_irr=2_000_000,
                    status="active",
                    stock_posture="sourced_after_payment",
                    sourcing_capacity_status="open",
                    minimum_shelf_life_months=6,
                ),
                Offer(
                    product_id=unavailable_alt_product.id,
                    supplier_id=supplier.id,
                    sku=f"ALT-UNAVAIL-{token}",
                    title_fa=f"پیشنهاد ناموجود {token}",
                    unit_label_fa="کیسه",
                    price_irr=2_000_000,
                    status="unavailable",
                    stock_posture="unavailable",
                    sourcing_capacity_status="open",
                    minimum_shelf_life_months=6,
                ),
            ]
        )
        await session.commit()
        return AltSeed(
            token=token,
            operator=operator,
            customer=customer,
            source_product_id=str(source_product.id),
            alternative_product_id=str(alt_product.id),
            unavailable_alternative_product_id=str(unavailable_alt_product.id),
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


async def test_operator_can_create_and_approve_an_alternative(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], alt_seed: AltSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: alt_seed.operator

    created = await client.post(
        "/api/v1/operator/product-alternatives",
        json={
            "source_product_id": alt_seed.source_product_id,
            "alternative_product_id": alt_seed.alternative_product_id,
            "rationale_fa": "دو محصول از نظر فرمول مشابه هستند",
            "rank": 1,
            "reason": "operator curation for launch catalog",
        },
    )
    assert created.status_code == 201
    alternative_id = created.json()["id"]
    assert await _audit_count("product_alternative.created", alternative_id) == 1

    approved = await client.post(
        f"/api/v1/operator/product-alternatives/{alternative_id}/approve",
        json={"reason": "reviewed and approved"},
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved"
    assert body["approved_by_operator_id"] == alt_seed.operator.id.__str__()
    assert body["approved_at"] is not None
    assert await _audit_count("product_alternative.approved", alternative_id) == 1

    # Replay-safe: approving an already-approved row is a no-op, not a
    # duplicate audit entry or an error.
    approved_again = await client.post(
        f"/api/v1/operator/product-alternatives/{alternative_id}/approve",
        json={"reason": "retry after client timeout"},
    )
    assert approved_again.status_code == 200
    assert await _audit_count("product_alternative.approved", alternative_id) == 1


async def test_self_reference_is_rejected(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], alt_seed: AltSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: alt_seed.operator

    response = await client.post(
        "/api/v1/operator/product-alternatives",
        json={
            "source_product_id": alt_seed.source_product_id,
            "alternative_product_id": alt_seed.source_product_id,
            "rationale_fa": "should be rejected",
            "reason": "attempted self reference",
        },
    )
    assert response.status_code == 422


async def test_duplicate_pair_is_rejected(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], alt_seed: AltSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: alt_seed.operator
    body = {
        "source_product_id": alt_seed.source_product_id,
        "alternative_product_id": alt_seed.alternative_product_id,
        "rationale_fa": "first proposal",
        "reason": "initial curation",
    }
    first = await client.post("/api/v1/operator/product-alternatives", json=body)
    assert first.status_code == 201
    second = await client.post("/api/v1/operator/product-alternatives", json=body)
    assert second.status_code == 409


async def test_non_operator_identity_is_forbidden(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], alt_seed: AltSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: alt_seed.customer

    response = await client.post(
        "/api/v1/operator/product-alternatives",
        json={
            "source_product_id": alt_seed.source_product_id,
            "alternative_product_id": alt_seed.alternative_product_id,
            "rationale_fa": "should be forbidden",
            "reason": "customer should not reach this",
        },
    )
    assert response.status_code == 403


async def test_public_endpoint_returns_only_approved_alternatives_with_live_offers(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], alt_seed: AltSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: alt_seed.operator

    async def _propose_and_approve(alternative_product_id: str, rank: int) -> str:
        created = await client.post(
            "/api/v1/operator/product-alternatives",
            json={
                "source_product_id": alt_seed.source_product_id,
                "alternative_product_id": alternative_product_id,
                "rationale_fa": "curated alternative",
                "rank": rank,
                "reason": "curation",
            },
        )
        alternative_id = created.json()["id"]
        await client.post(
            f"/api/v1/operator/product-alternatives/{alternative_id}/approve",
            json={"reason": "approved"},
        )
        return alternative_id

    approved_id = await _propose_and_approve(alt_seed.alternative_product_id, rank=0)
    # Approved, but its product has no currently-available offer -- must be
    # revalidated and excluded at read time, not shown as a dead-end.
    await _propose_and_approve(alt_seed.unavailable_alternative_product_id, rank=1)

    # A third, merely-proposed (not approved) alternative must never appear.
    async with SessionFactory() as session:
        never_approved_product = Product(name_fa=f"هرگز تایید نشده {alt_seed.token}")
        session.add(never_approved_product)
        await session.flush()
        session.add(
            ProductAlternative(
                source_product_id=uuid.UUID(alt_seed.source_product_id),
                alternative_product_id=never_approved_product.id,
                status="proposed",
                rationale_fa="not yet approved",
                proposed_by_operator_id=alt_seed.operator.id,
            )
        )
        await session.commit()

    app.dependency_overrides.clear()
    response = await client.get(
        f"/api/v1/catalog/products/{alt_seed.source_product_id}/alternatives"
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == approved_id
    assert items[0]["offer"]["id"]
    assert set(items[0].keys()) == {
        "id",
        "rank",
        "rationale_fa",
        "compatibility_notes_fa",
        "offer",
    }


async def test_update_is_blocked_once_retired(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], alt_seed: AltSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: alt_seed.operator

    created = await client.post(
        "/api/v1/operator/product-alternatives",
        json={
            "source_product_id": alt_seed.source_product_id,
            "alternative_product_id": alt_seed.alternative_product_id,
            "rationale_fa": "initial",
            "reason": "curation",
        },
    )
    alternative_id = created.json()["id"]

    retired = await client.post(
        f"/api/v1/operator/product-alternatives/{alternative_id}/retire",
        json={"reason": "no longer relevant"},
    )
    assert retired.status_code == 200
    assert retired.json()["status"] == "retired"

    # Idempotent retire: retiring again must not error or double-audit.
    retired_again = await client.post(
        f"/api/v1/operator/product-alternatives/{alternative_id}/retire",
        json={"reason": "retry"},
    )
    assert retired_again.status_code == 200
    assert await _audit_count("product_alternative.retired", alternative_id) == 1

    blocked_update = await client.patch(
        f"/api/v1/operator/product-alternatives/{alternative_id}",
        json={"rationale_fa": "trying to edit a retired row", "reason": "should fail"},
    )
    assert blocked_update.status_code == 409


async def test_unknown_alternative_id_is_404_not_found(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], alt_seed: AltSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: alt_seed.operator

    response = await client.post(
        f"/api/v1/operator/product-alternatives/{uuid.uuid4()}/approve",
        json={"reason": "does not exist"},
    )
    assert response.status_code == 404
