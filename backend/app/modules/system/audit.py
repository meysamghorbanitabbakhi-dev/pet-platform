from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.system.models import OperatorAuditLog


def record_operator_action(
    session: AsyncSession,
    *,
    operator_identity_id: UUID,
    action: str,
    resource_type: str,
    resource_id: str,
    request_id: str,
    reason: str | None,
    before_facts: dict[str, Any] | None,
    after_facts: dict[str, Any] | None,
    source_ip: str | None,
) -> None:
    session.add(
        OperatorAuditLog(
            operator_identity_id=operator_identity_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            reason=reason,
            before_facts=before_facts,
            after_facts=after_facts,
            source_ip=source_ip,
        )
    )
