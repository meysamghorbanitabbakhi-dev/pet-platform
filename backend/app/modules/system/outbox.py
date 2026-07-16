from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.time import utc_now
from app.modules.system.models import OutboxEvent

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]


def add_outbox_event(session: AsyncSession, event: DomainEvent) -> UUID:
    now = utc_now()
    event_id = uuid4()
    record = OutboxEvent(
        event_id=event_id,
        event_type=event.event_type,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        payload=event.payload,
        occurred_at=now,
        available_at=now,
    )
    session.add(record)
    return event_id


class OutboxDispatcher:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], batch_size: int = 50
    ) -> None:
        self._session_factory = session_factory
        self._batch_size = batch_size
        self._handlers: dict[str, list[EventHandler]] = {}

    def register(self, event_type: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def dispatch_batch(self) -> int:
        records = await self._claim_batch()
        for record in records:
            await self._dispatch_one(record)
        return len(records)

    async def _claim_batch(self) -> list[OutboxEvent]:
        now = utc_now()
        async with self._session_factory() as session, session.begin():
            statement = (
                select(OutboxEvent)
                .where(
                    OutboxEvent.published_at.is_(None),
                    OutboxEvent.available_at <= now,
                    (OutboxEvent.claimed_until.is_(None) | (OutboxEvent.claimed_until < now)),
                )
                .order_by(OutboxEvent.occurred_at)
                .limit(self._batch_size)
                .with_for_update(skip_locked=True)
            )
            records = list((await session.scalars(statement)).all())
            for record in records:
                record.claimed_until = now + timedelta(minutes=2)
                record.attempts += 1
            return records

    async def _dispatch_one(self, claimed: OutboxEvent) -> None:
        handlers = self._handlers.get(claimed.event_type, [])
        try:
            if not handlers:
                raise RuntimeError(f"no handler registered for {claimed.event_type}")
            for handler in handlers:
                await handler(claimed.payload)
        except Exception as exc:
            await self._mark_failed(claimed.id, str(exc))
        else:
            await self._mark_published(claimed.id)

    async def _mark_published(self, record_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            record = await session.get(OutboxEvent, record_id, with_for_update=True)
            if record is not None and record.published_at is None:
                record.published_at = utc_now()
                record.claimed_until = None
                record.last_error = None

    async def _mark_failed(self, record_id: UUID, error: str) -> None:
        async with self._session_factory() as session, session.begin():
            record = await session.get(OutboxEvent, record_id, with_for_update=True)
            if record is not None and record.published_at is None:
                delay_seconds = min(3600, 2 ** min(record.attempts, 10))
                record.available_at = utc_now() + timedelta(seconds=delay_seconds)
                record.claimed_until = None
                record.last_error = error[:4000]
