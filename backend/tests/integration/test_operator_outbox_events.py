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
from app.modules.identity.models import AuthIdentity
from app.modules.system.models import OperatorAuditLog, OutboxEvent
from app.modules.system.outbox import DomainEvent, add_outbox_event
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
class OutboxSeed:
    operator: AuthIdentity
    customer: AuthIdentity


@pytest.fixture()
async def outbox_seed() -> OutboxSeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        operator = AuthIdentity(
            identity_type="operator", mobile_e164=f"+98915{token[:7]}", status="active"
        )
        customer = AuthIdentity(
            identity_type="customer", mobile_e164=f"+98916{token[:7]}", status="active"
        )
        session.add_all([operator, customer])
        await session.commit()
        return OutboxSeed(operator=operator, customer=customer)


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def _seed_dead_letter_event() -> uuid.UUID:
    aggregate_id = f"dead-letter-{uuid.uuid4().hex}"
    async with SessionFactory() as session:
        event_id = add_outbox_event(
            session,
            DomainEvent(
                event_type="unknown.event",
                aggregate_type="unknown",
                aggregate_id=aggregate_id,
                payload={"probe": aggregate_id},
            ),
        )
        record = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        assert record is not None
        record.status = "dead_letter"
        record.attempts = 5
        record.last_error = "no handler registered for unknown.event"
        await session.commit()
        return record.id


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


async def test_list_outbox_events_defaults_to_dead_letter_status(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], outbox_seed: OutboxSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: outbox_seed.operator
    record_id = await _seed_dead_letter_event()

    response = await client.get("/api/v1/operator/outbox/events")
    assert response.status_code == 200
    body = response.json()
    assert "has_more" in body
    ids = {item["id"] for item in body["items"]}
    assert str(record_id) in ids
    matched = next(item for item in body["items"] if item["id"] == str(record_id))
    assert matched["status"] == "dead_letter"
    assert matched["disposition"] == "unregistered"
    assert matched["attempts"] == 5
    assert matched["last_error"] is not None


async def test_list_outbox_events_rejects_unknown_status(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], outbox_seed: OutboxSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: outbox_seed.operator

    response = await client.get(
        "/api/v1/operator/outbox/events", params={"status": "not_a_real_status"}
    )
    assert response.status_code == 422


async def test_list_outbox_events_requires_operator_role(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], outbox_seed: OutboxSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: outbox_seed.customer

    response = await client.get("/api/v1/operator/outbox/events")
    assert response.status_code == 403


async def test_replay_dead_letter_event_resets_it_to_pending(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], outbox_seed: OutboxSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: outbox_seed.operator
    record_id = await _seed_dead_letter_event()

    response = await client.post(
        f"/api/v1/operator/outbox/events/{record_id}/replay",
        json={"reason": "handler bug fixed upstream, safe to redeliver"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["attempts"] == 0
    assert body["last_error"] is None

    async with SessionFactory() as session:
        record = await session.get(OutboxEvent, record_id)
        assert record is not None
        assert record.status == "pending"
        assert record.claimed_until is None
    assert await _audit_count("outbox_event.replayed", str(record_id)) == 1


async def test_replay_rejects_event_that_is_not_failed_or_dead_letter(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], outbox_seed: OutboxSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: outbox_seed.operator
    aggregate_id = f"already-published-{uuid.uuid4().hex}"
    async with SessionFactory() as session:
        event_id = add_outbox_event(
            session,
            DomainEvent(
                event_type="order.awaiting_payment",
                aggregate_type="order",
                aggregate_id=aggregate_id,
                payload={},
            ),
        )
        record = await session.scalar(select(OutboxEvent).where(OutboxEvent.event_id == event_id))
        assert record is not None
        record.status = "published"
        await session.commit()
        record_id = record.id

    response = await client.post(
        f"/api/v1/operator/outbox/events/{record_id}/replay",
        json={"reason": "should be rejected regardless"},
    )
    assert response.status_code == 409


async def test_replay_unknown_event_is_404(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], outbox_seed: OutboxSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: outbox_seed.operator

    response = await client.post(
        f"/api/v1/operator/outbox/events/{uuid.uuid4()}/replay",
        json={"reason": "probing an id that does not exist"},
    )
    assert response.status_code == 404


async def test_replay_requires_operator_role(
    app_and_client: tuple[FastAPI, httpx.AsyncClient], outbox_seed: OutboxSeed
) -> None:
    app, client = app_and_client
    app.dependency_overrides[get_current_identity] = lambda: outbox_seed.customer
    record_id = await _seed_dead_letter_event()

    response = await client.post(
        f"/api/v1/operator/outbox/events/{record_id}/replay",
        json={"reason": "customer should never reach this"},
    )
    assert response.status_code == 403
