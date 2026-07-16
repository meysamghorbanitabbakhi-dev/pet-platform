from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.system.models import IdempotencyRecord


class IdempotencyConflictError(Exception):
    """The same key was reused for a different request."""


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    state: Literal["acquired", "in_progress", "replay"]
    response_status: int | None = None
    response_body: dict[str, Any] | None = None


def canonical_request_hash(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


async def claim_idempotency_key(
    session: AsyncSession,
    *,
    scope: str,
    key: str,
    request_body: dict[str, Any],
    lock_for: timedelta = timedelta(minutes=2),
    retain_for: timedelta = timedelta(hours=24),
) -> IdempotencyClaim:
    now = utc_now()
    request_hash = canonical_request_hash(request_body)
    statement = (
        insert(IdempotencyRecord)
        .values(
            scope=scope,
            idempotency_key=key,
            request_hash=request_hash,
            state="processing",
            locked_until=now + lock_for,
            expires_at=now + retain_for,
        )
        .on_conflict_do_nothing(index_elements=["scope", "idempotency_key"])
        .returning(IdempotencyRecord.id)
    )
    inserted_id = await session.scalar(statement)
    if inserted_id is not None:
        return IdempotencyClaim(state="acquired")

    record = await session.scalar(
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == key,
        )
        .with_for_update()
    )
    if record is None:
        raise RuntimeError("idempotency record disappeared during claim")
    if record.request_hash != request_hash:
        raise IdempotencyConflictError("idempotency key was already used for another request")
    if record.state == "completed":
        return IdempotencyClaim(
            state="replay",
            response_status=record.response_status,
            response_body=record.response_body,
        )
    if record.locked_until > now:
        return IdempotencyClaim(state="in_progress")

    record.state = "processing"
    record.locked_until = now + lock_for
    record.expires_at = now + retain_for
    return IdempotencyClaim(state="acquired")


async def complete_idempotent_request(
    session: AsyncSession,
    *,
    scope: str,
    key: str,
    response_status: int,
    response_body: dict[str, Any],
) -> None:
    record = await session.scalar(
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == key,
        )
        .with_for_update()
    )
    if record is None:
        raise RuntimeError("cannot complete an unclaimed idempotency key")
    record.state = "completed"
    record.response_status = response_status
    record.response_body = response_body
    record.locked_until = utc_now()
