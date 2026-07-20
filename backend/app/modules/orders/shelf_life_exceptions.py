from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from app.common.time import add_months, utc_now
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.orders.models import Order, OrderLine
from app.modules.system.outbox import DomainEvent, add_outbox_event
from app.modules.trust.models import SourcedUnitEvidence, SupplierAssurance


class ShelfLifeException(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An operator-proposed exception to the offer's minimum shelf-life
    guarantee (Workstream 2E) -- created only when a sourced unit's real
    exact_expiry_date falls short of what confirm_sourced_unit's hard block
    requires. The customer must explicitly accept or decline; there is no
    fulfillment path around this (SourcedUnitEvidence, which
    project_delivered_order requires, is only created on acceptance).

    Refunds are operator-attested, never an automatic payment-gateway
    reversal -- same explicit product decision as OrderCancellation (2B),
    see refund_attestation.py for the shared mechanism.
    """

    __tablename__ = "orders_shelf_life_exceptions"
    __table_args__ = (
        # At most one *active* ('proposed') exception per order line at a
        # time -- enforced by a partial unique index
        # (uq_shelf_life_exceptions_one_active_per_order_line, see the
        # 20260720_0038 migration), not declared here in SQLAlchemy
        # metadata, matching this codebase's existing convention for
        # partial indexes (see purchasing_batches' equivalent). A
        # resolved (declined/expired) proposal does not block a revised
        # re-proposal for the same line -- see ADR-007's amendment.
        CheckConstraint(
            "status IN ('proposed','accepted','declined','expired')", name="valid_status"
        ),
        CheckConstraint("additional_discount_irr > 0", name="positive_discount"),
        CheckConstraint(
            "refund_status IN ('not_applicable','owed','operator_attested')",
            name="valid_refund_status",
        ),
        CheckConstraint(
            "refund_amount_irr IS NULL OR refund_amount_irr > 0", name="positive_refund_amount"
        ),
    )

    order_line_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders_order_lines.id"), nullable=False, index=True
    )
    proposed_exact_expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    additional_discount_irr: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("trust_evidence_files.id"), nullable=False
    )
    proposed_by_operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), nullable=False
    )
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    respond_by: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="proposed", nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_by_customer_identity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
    refund_status: Mapped[str] = mapped_column(
        String(20), default="not_applicable", nullable=False
    )
    refund_amount_irr: Mapped[int | None] = mapped_column(Integer)
    refund_attested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refund_attested_by_operator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
    refund_evidence_file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("trust_evidence_files.id")
    )
    refund_reference: Mapped[str | None] = mapped_column(String(300))


class ShelfLifeExceptionError(Exception):
    pass


async def propose_shelf_life_exception(
    session: AsyncSession,
    *,
    order_line: OrderLine,
    order: Order,
    minimum_shelf_life_months: int,
    operator_id: UUID,
    proposed_exact_expiry_date: date,
    additional_discount_irr: int,
    reason: str,
    evidence_file_id: UUID,
    response_window_hours: int,
) -> ShelfLifeException:
    """Propose an exception for a line whose real expiry falls short of the
    offer's guarantee. Rejects a proposal for a line that would actually
    pass the normal guarantee (confirm_sourced_unit is the right path for
    that), one that's already sourced, or one that already has an active
    (still 'proposed') exception -- a resolved (declined/expired) prior
    exception does not block a revised re-proposal, see ADR-007's
    amendment. response_window_hours has no in-code default: the caller
    (the operator route) is expected to supply
    settings.shelf_life_exception_response_window_hours, keeping the
    number operator-configurable rather than hardcoded here."""
    if order.delivery_commitment_at is None:
        raise ShelfLifeExceptionError("order_has_no_delivery_commitment")
    minimum_date = add_months(order.delivery_commitment_at.date(), minimum_shelf_life_months)
    if proposed_exact_expiry_date >= minimum_date:
        raise ShelfLifeExceptionError("expiry_meets_guarantee_no_exception_needed")
    already_sourced = await session.scalar(
        select(SourcedUnitEvidence.id).where(SourcedUnitEvidence.order_line_id == order_line.id)
    )
    if already_sourced is not None:
        raise ShelfLifeExceptionError("order_line_already_sourced")
    if additional_discount_irr <= 0:
        # Shipping a product that falls short of the promised guarantee
        # without any compensation is not a real exception, it's just a
        # broken guarantee -- see ADR-007's amendment.
        raise ShelfLifeExceptionError("additional_discount_irr_must_be_positive")
    active = await session.scalar(
        select(ShelfLifeException).where(
            ShelfLifeException.order_line_id == order_line.id,
            ShelfLifeException.status == "proposed",
        )
    )
    if active is not None:
        raise ShelfLifeExceptionError("exception_already_exists_for_line")
    already_refunded = await session.scalar(
        select(ShelfLifeException.id).where(
            ShelfLifeException.order_line_id == order_line.id,
            ShelfLifeException.refund_status == "operator_attested",
        )
    )
    if already_refunded is not None:
        # A prior exception's refund for this exact line has already been
        # paid out (declined/expired -> operator attested the full-line
        # refund). Re-offering the line now would let the customer both
        # keep that refund and receive/accept the product -- a genuine
        # double payout, not merely a bookkeeping inconsistency. The
        # operator's only path forward here is a new order line (a fresh
        # purchase), not a further exception against this one.
        raise ShelfLifeExceptionError("order_line_refund_already_paid")
    now = utc_now()
    exception = ShelfLifeException(
        order_line_id=order_line.id,
        proposed_exact_expiry_date=proposed_exact_expiry_date,
        additional_discount_irr=additional_discount_irr,
        reason=reason,
        evidence_file_id=evidence_file_id,
        proposed_by_operator_id=operator_id,
        proposed_at=now,
        respond_by=now + timedelta(hours=response_window_hours),
        status="proposed",
    )
    session.add(exception)
    await session.flush()
    add_outbox_event(
        session,
        DomainEvent(
            event_type="orders.shelf_life_exception_proposed",
            aggregate_type="order_line",
            aggregate_id=str(order_line.id),
            payload={
                "shelf_life_exception_id": str(exception.id),
                "order_id": str(order.id),
                "order_line_id": str(order_line.id),
                "household_id": str(order.household_id),
                "respond_by": exception.respond_by.isoformat(),
            },
        ),
    )
    return exception


def _expire_if_past_deadline(
    exception: ShelfLifeException, order_line: OrderLine, now: datetime
) -> bool:
    if now <= exception.respond_by:
        return False
    exception.status = "expired"
    exception.responded_at = now
    exception.refund_status = "owed"
    exception.refund_amount_irr = order_line.line_total_irr
    order_line.excluded_from_delivery_at = now
    return True


async def _supersede_prior_owed_refunds(
    session: AsyncSession, *, order_line_id: UUID, keep_exception_id: UUID
) -> None:
    """A line can cycle through several proposals (re-proposal after
    decline/expiry, ADR-007's amendment); only one full-line refund should
    ever be payable for it at a time. Whenever a proposal newly reaches a
    terminal state that sets its own 'owed' refund (or supersedes the need
    for one, on accept), any *other* exception for the same line still
    sitting at 'owed' from an earlier cycle must stop being payable --
    otherwise more than one of them could be attested, a genuine double
    liability. 'superseded' is a distinct terminal state from
    'operator_attested' precisely so attest_refund's existing
    refund_status == 'owed' check rejects it by construction, not a new
    runtime guard bolted on top."""
    await session.execute(
        update(ShelfLifeException)
        .where(
            ShelfLifeException.order_line_id == order_line_id,
            ShelfLifeException.id != keep_exception_id,
            ShelfLifeException.refund_status == "owed",
        )
        .values(refund_status="superseded")
    )


async def accept_shelf_life_exception(
    session: AsyncSession,
    *,
    exception: ShelfLifeException,
    order_line: OrderLine,
    supplier_id: UUID,
    customer_identity_id: UUID,
) -> ShelfLifeException:
    """Accept the proposed shorter expiry. Creates the SourcedUnitEvidence
    that unblocks delivery projection for this line -- there is no other
    path to it once an exception exists. Idempotent: accepting an
    already-accepted exception returns it unchanged.

    Caller must have already row-locked `exception` (with_for_update) so
    this and a concurrent decline/expire of the same exception serialize
    correctly.
    """
    if exception.status != "proposed":
        if exception.status == "accepted":
            return exception
        raise ShelfLifeExceptionError(f"exception_not_open_for_response:{exception.status}")
    now = utc_now()
    if _expire_if_past_deadline(exception, order_line, now):
        await _supersede_prior_owed_refunds(
            session, order_line_id=order_line.id, keep_exception_id=exception.id
        )
        await session.flush()
        raise ShelfLifeExceptionError("exception_response_window_expired")
    assurance = await session.scalar(
        select(SupplierAssurance).where(
            SupplierAssurance.supplier_id == supplier_id,
            SupplierAssurance.active.is_(True),
            SupplierAssurance.valid_from <= now.date(),
            (SupplierAssurance.valid_until.is_(None))
            | (SupplierAssurance.valid_until >= now.date()),
        )
    )
    if assurance is None:
        raise ShelfLifeExceptionError("active_supplier_assurance_required")
    exception.status = "accepted"
    exception.responded_at = now
    exception.responded_by_customer_identity_id = customer_identity_id
    if exception.additional_discount_irr > 0:
        exception.refund_status = "owed"
        exception.refund_amount_irr = exception.additional_discount_irr
    # Restores deliverability: a prior proposal for this same line may
    # have been declined or allowed to expire, which sets this flag (see
    # _expire_if_past_deadline and decline_shelf_life_exception below) --
    # left set, project_delivered_order would permanently skip this line
    # despite the SourcedUnitEvidence just added below making it genuinely
    # deliverable now. See ADR-007's amendment.
    order_line.excluded_from_delivery_at = None
    # already_refunded (propose_shelf_life_exception) should already have
    # blocked ever reaching accept for a line whose refund was paid
    # *before* this proposal existed; this also covers attestation
    # happening concurrently with this acceptance.
    await _supersede_prior_owed_refunds(
        session, order_line_id=order_line.id, keep_exception_id=exception.id
    )
    session.add(
        SourcedUnitEvidence(
            order_line_id=order_line.id,
            exact_expiry_date=exception.proposed_exact_expiry_date,
            supplier_country_snapshot=order_line.supplier_country_snapshot,
            authenticity_basis="shelf_life_exception_accepted",
            supplier_assurance_id=assurance.id,
            confirmed_at=now,
            recorded_by_operator_id=exception.proposed_by_operator_id,
        )
    )
    await session.flush()
    return exception


async def decline_shelf_life_exception(
    session: AsyncSession,
    *,
    exception: ShelfLifeException,
    order_line: OrderLine,
    customer_identity_id: UUID,
) -> ShelfLifeException:
    """Decline the proposed shorter expiry: the line will not be
    delivered and its full line total is owed back. Idempotent: declining
    an already-declined exception returns it unchanged.

    Caller must have already row-locked `exception` (with_for_update).
    """
    if exception.status != "proposed":
        if exception.status == "declined":
            return exception
        raise ShelfLifeExceptionError(f"exception_not_open_for_response:{exception.status}")
    now = utc_now()
    if _expire_if_past_deadline(exception, order_line, now):
        await _supersede_prior_owed_refunds(
            session, order_line_id=order_line.id, keep_exception_id=exception.id
        )
        await session.flush()
        raise ShelfLifeExceptionError("exception_response_window_expired")
    exception.status = "declined"
    exception.responded_at = now
    exception.responded_by_customer_identity_id = customer_identity_id
    exception.refund_status = "owed"
    exception.refund_amount_irr = order_line.line_total_irr
    order_line.excluded_from_delivery_at = now
    # Superseding here too (not just on accept): a line can be declined
    # more than once across successive re-proposal cycles, and each
    # decline sets its own fresh 'owed' full-line refund -- without this,
    # an earlier cycle's already-owed refund for the same line would
    # remain independently attestable alongside this one.
    await _supersede_prior_owed_refunds(
        session, order_line_id=order_line.id, keep_exception_id=exception.id
    )
    await session.flush()
    return exception


async def expire_stale_shelf_life_exceptions(
    session_factory: async_sessionmaker[AsyncSession], *, batch_size: int = 100
) -> int:
    """Scheduler sweep: any exception still 'proposed' past its
    respond_by deadline becomes 'expired' with a full-line refund owed,
    same as an explicit decline. Runs unconditionally (not gated behind a
    settings flag) -- propose/accept/decline is a live capability, not a
    disabled-by-default one like reserve-now or late-delivery credit.
    """
    now = utc_now()
    async with session_factory() as session:
        exceptions = list(
            (
                await session.scalars(
                    select(ShelfLifeException)
                    .where(
                        ShelfLifeException.status == "proposed",
                        ShelfLifeException.respond_by < now,
                    )
                    .order_by(ShelfLifeException.respond_by)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        expired = 0
        for exception in exceptions:
            order_line = await session.get(OrderLine, exception.order_line_id)
            if order_line is None:
                continue
            if _expire_if_past_deadline(exception, order_line, now):
                await _supersede_prior_owed_refunds(
                    session, order_line_id=order_line.id, keep_exception_id=exception.id
                )
                expired += 1
        await session.commit()
        return expired
