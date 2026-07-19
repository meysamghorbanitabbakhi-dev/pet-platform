from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.common.time import utc_now


class RefundOwed(Protocol):
    """Structural shape shared by OrderCancellation (2B) and
    ShelfLifeException (2E) -- both record a refund the merchant owes the
    customer, attested manually by an operator rather than an automatic
    payment-gateway reversal (explicit product decision)."""

    refund_status: str
    refund_attested_at: datetime | None
    refund_attested_by_operator_id: UUID | None
    refund_evidence_file_id: UUID | None
    refund_reference: str | None


class RefundAttestationError(Exception):
    pass


def attest_refund(
    record: RefundOwed,
    *,
    operator_id: UUID,
    evidence_id: UUID,
    reference: str | None,
) -> None:
    """Record that an operator manually paid back a refund already marked
    'owed'. Replay-safe: attesting an already-attested record is a no-op."""
    if record.refund_status == "operator_attested":
        return
    if record.refund_status != "owed":
        raise RefundAttestationError(f"refund_not_owed:{record.refund_status}")
    record.refund_status = "operator_attested"
    record.refund_attested_at = utc_now()
    record.refund_attested_by_operator_id = operator_id
    record.refund_evidence_file_id = evidence_id
    record.refund_reference = reference
