from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.system.models import WebhookInboxEvent


def record_webhook(
    session: AsyncSession,
    *,
    provider: str,
    provider_event_id: str,
    payload: dict[str, Any],
    headers: dict[str, Any],
    signature_valid: bool,
    event_type: str | None = None,
) -> WebhookInboxEvent:
    event = WebhookInboxEvent(
        provider=provider,
        provider_event_id=provider_event_id,
        event_type=event_type,
        payload=payload,
        headers=headers,
        signature_valid=signature_valid,
        processing_status="received" if signature_valid else "rejected",
    )
    session.add(event)
    return event
