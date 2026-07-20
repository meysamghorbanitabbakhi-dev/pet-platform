from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.catalog.models import Offer
from app.modules.orders.models import OrderLine
from app.modules.purchasing.models import (
    PurchaseBatch,
    PurchaseBatchAllocation,
    PurchaseBatchEvent,
)

_ROLLING_DEADLINE = timedelta(days=7)


class PurchasingError(Exception):
    pass


async def allocate_order_line_to_batch(
    session: AsyncSession, *, order_line: OrderLine, offer: Offer
) -> PurchaseBatchAllocation:
    """Assign order_line's sourcing to a purchase batch, opening one if needed.

    Idempotent/replay-safe: allocating an already-allocated line returns the
    existing allocation unchanged, never a second one.
    """
    existing = await session.scalar(
        select(PurchaseBatchAllocation).where(
            PurchaseBatchAllocation.order_line_id == order_line.id
        )
    )
    if existing is not None:
        return existing

    batch = await _find_or_open_batch(session, offer=offer)
    return await _allocate_into(session, batch=batch, order_line=order_line)


async def _find_or_open_batch(session: AsyncSession, *, offer: Offer) -> PurchaseBatch:
    now = utc_now()
    if offer.sourcing_route == "individual":
        # Never pooled -- always a fresh, dedicated batch (Decision 0.10).
        batch = PurchaseBatch(
            offer_id=offer.id,
            grouping_mode="individual",
            status="open",
            deadline_at=None,
            minimum_viable_threshold_quantity=1,
        )
        session.add(batch)
        await session.flush()
        session.add(_opened_event(batch.id, now))
        return batch

    existing_batch = await session.scalar(
        select(PurchaseBatch)
        .where(
            PurchaseBatch.offer_id == offer.id,
            PurchaseBatch.grouping_mode == "aggregated",
            PurchaseBatch.status == "open",
        )
        .order_by(PurchaseBatch.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if existing_batch is not None:
        return existing_batch

    if offer.default_batch_threshold_quantity is None:
        # An unconfigured threshold used to silently fall back to 1 --
        # "no real aggregation benefit," per the offer's own comment. That
        # let an offer accidentally left on the aggregated route commit
        # supplier money after a single order, defeating the entire point
        # of pooling. An operator must explicitly configure a real number
        # (via PATCH /offers/{id}/sourcing-config) before this route can
        # open a batch; nothing here guesses one.
        raise PurchasingError(
            f"offer {offer.id} is on the aggregated sourcing route with no "
            "default_batch_threshold_quantity configured"
        )

    # No open batch was visible -- try to open one. A concurrent transaction
    # may be doing the same thing right now; the partial unique index (one
    # open aggregated batch per offer) makes only one of us win. The insert
    # attempt runs inside a SAVEPOINT (begin_nested): a conflict there must
    # only unwind this one insert, never the outer transaction -- this
    # function runs mid-way through payment verification, which has already
    # made other changes in the same session that must survive.
    candidate = PurchaseBatch(
        offer_id=offer.id,
        grouping_mode="aggregated",
        status="open",
        deadline_at=now + _ROLLING_DEADLINE,
        minimum_viable_threshold_quantity=offer.default_batch_threshold_quantity,
    )
    try:
        async with session.begin_nested():
            session.add(candidate)
            await session.flush()
    except IntegrityError:
        # begin_nested()'s rollback already detaches `candidate` from the
        # session; nothing further to clean up here.
        winner = await session.scalar(
            select(PurchaseBatch)
            .where(
                PurchaseBatch.offer_id == offer.id,
                PurchaseBatch.grouping_mode == "aggregated",
                PurchaseBatch.status == "open",
            )
            .order_by(PurchaseBatch.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        if winner is None:
            raise PurchasingError(
                "batch open race failed and no winner is visible"
            ) from None
        return winner
    session.add(_opened_event(candidate.id, now))
    return candidate


async def _allocate_into(
    session: AsyncSession, *, batch: PurchaseBatch, order_line: OrderLine
) -> PurchaseBatchAllocation:
    now = utc_now()
    batch.allocated_quantity += order_line.quantity
    if (
        batch.threshold_reached_at is None
        and batch.allocated_quantity >= batch.minimum_viable_threshold_quantity
    ):
        batch.threshold_reached_at = now
        session.add(
            PurchaseBatchEvent(
                purchase_batch_id=batch.id,
                event_type="threshold_reached",
                occurred_at=now,
                operator_identity_id=None,
            )
        )
    allocation = PurchaseBatchAllocation(
        purchase_batch_id=batch.id,
        order_line_id=order_line.id,
        quantity=order_line.quantity,
        allocated_at=now,
    )
    session.add(allocation)
    await session.flush()
    return allocation


def _opened_event(batch_id: UUID, now: datetime) -> PurchaseBatchEvent:
    return PurchaseBatchEvent(
        purchase_batch_id=batch_id,
        event_type="opened",
        occurred_at=now,
        operator_identity_id=None,
    )


async def commit_batch(
    session: AsyncSession,
    *,
    batch: PurchaseBatch,
    operator_id: UUID,
    evidence_file_id: UUID,
    commitment_reference: str | None,
    reason: str,
) -> PurchaseBatch:
    """Record the durable supplier financial-commitment fact. Replay-safe:
    committing an already-committed batch is a no-op, not a duplicate event."""
    if batch.status == "cancelled":
        raise PurchasingError("batch is cancelled")
    if batch.status == "committed":
        return batch
    now = utc_now()
    batch.status = "committed"
    batch.committed_at = now
    batch.committed_by_operator_id = operator_id
    batch.commitment_evidence_file_id = evidence_file_id
    batch.commitment_reference = commitment_reference
    session.add(
        PurchaseBatchEvent(
            purchase_batch_id=batch.id,
            event_type="committed",
            occurred_at=now,
            reason=reason,
            operator_identity_id=operator_id,
        )
    )
    await session.flush()
    return batch


async def cancel_batch(
    session: AsyncSession, *, batch: PurchaseBatch, operator_id: UUID, reason: str
) -> PurchaseBatch:
    """Operator abandons an open batch that will never be committed --
    e.g. a misconfigured or no-longer-sourceable offer (ADR-006's deferred
    "future ADR ... if/when a real operational need arises," triggered by
    the gap-closure program). Replay-safe: cancelling an already-cancelled
    batch is a no-op.

    Deliberately conservative: only a batch with no active (un-voided)
    allocations can be cancelled this way. A batch still holding paid
    orders' allocations must have each of those orders cancelled through
    the customer-cancellation path first (which voids its allocation) --
    Decision 0.12's "must not silently cancel paid orders" means bulk-
    detaching live orders from their batch is not a decision this function
    gets to make unilaterally. Caller must have already row-locked `batch`.
    """
    if batch.status == "cancelled":
        return batch
    if batch.status == "committed":
        raise PurchasingError("batch is already committed")
    if batch.allocated_quantity != 0:
        raise PurchasingError("batch has active allocations and cannot be cancelled directly")
    now = utc_now()
    batch.status = "cancelled"
    batch.cancelled_at = now
    batch.cancelled_by_operator_id = operator_id
    session.add(
        PurchaseBatchEvent(
            purchase_batch_id=batch.id,
            event_type="cancelled",
            occurred_at=now,
            reason=reason,
            operator_identity_id=operator_id,
        )
    )
    await session.flush()
    return batch


async def is_order_cancellation_eligible(session: AsyncSession, *, order_id: UUID) -> bool:
    """True iff no order line in this order has a committed batch allocation.

    Read-only convenience check with no locking -- safe for a GET response
    (e.g. "should the customer see a Cancel button"), but not sufficient by
    itself to gate the actual cancellation write: use
    void_allocations_for_cancelled_order for that, which re-checks under
    row locks so the cancel-vs-commit race is linearizable.
    """
    committed_line = await session.scalar(
        select(OrderLine.id)
        .join(
            PurchaseBatchAllocation, PurchaseBatchAllocation.order_line_id == OrderLine.id
        )
        .join(PurchaseBatch, PurchaseBatch.id == PurchaseBatchAllocation.purchase_batch_id)
        .where(OrderLine.order_id == order_id, PurchaseBatch.committed_at.is_not(None))
        .limit(1)
    )
    return committed_line is None


async def void_allocations_for_cancelled_order(
    session: AsyncSession, *, order_id: UUID
) -> None:
    """Release this order's allocations from their batches for a customer
    cancellation (Workstream 2B). Called by orders.cancellation as an
    explicit command rather than writing PurchaseBatch/PurchaseBatchAllocation
    directly, per module-boundaries.md (a module must not update another
    module's owned tables directly).

    Raises PurchasingError if any implicated batch has already been
    committed -- the caller must treat that as cancellation-not-eligible
    and roll back, not partially void the rest.

    Every implicated batch is locked (sorted by id, to avoid deadlocking
    against a concurrent call locking the same batches in a different
    order) before checking commitment, so this is linearizable against
    commit_batch: whichever transaction acquires a given batch's lock
    first is authoritative, and the loser re-reads the up-to-date
    committed_at once unblocked.

    Batch-level cancellation/re-commitment after a voided allocation is
    out of scope for this pass, same as ADR-006's existing exclusions --
    an aggregated batch with other, still-active lines remains open and
    committable exactly as before.
    """
    allocations = list(
        (
            await session.scalars(
                select(PurchaseBatchAllocation)
                .join(OrderLine, OrderLine.id == PurchaseBatchAllocation.order_line_id)
                .where(
                    OrderLine.order_id == order_id,
                    PurchaseBatchAllocation.voided_at.is_(None),
                )
            )
        ).all()
    )
    if not allocations:
        return
    batch_ids = sorted({allocation.purchase_batch_id for allocation in allocations})
    batches: dict[UUID, PurchaseBatch] = {}
    for batch_id in batch_ids:
        batch = await session.scalar(
            select(PurchaseBatch).where(PurchaseBatch.id == batch_id).with_for_update()
        )
        if batch is None:
            raise PurchasingError("allocated batch is missing")
        if batch.committed_at is not None:
            raise PurchasingError("batch is already committed")
        batches[batch_id] = batch
    now = utc_now()
    for allocation in allocations:
        batch = batches[allocation.purchase_batch_id]
        batch.allocated_quantity -= allocation.quantity
        allocation.voided_at = now
    for batch in batches.values():
        session.add(
            PurchaseBatchEvent(
                purchase_batch_id=batch.id,
                event_type="allocation_voided",
                occurred_at=now,
                reason=f"order {order_id} cancelled by customer",
                operator_identity_id=None,
            )
        )
    await session.flush()
