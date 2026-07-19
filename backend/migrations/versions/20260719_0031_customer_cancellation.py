"""Customer cancellation before supplier commitment (Workstream 2B).

Revision ID: 20260719_0031
Revises: 20260719_0030

orders_cancellations: at most one per order (unique on order_id). Holds an
immutable snapshot of the order/lines at cancellation time and the
refund-owed fact -- refund_status starts 'owed' and only becomes
'operator_attested' once an operator records evidence the money was
actually paid back (explicit product decision: no automatic
payment-gateway reversal call).

purchasing_batch_allocations gains voided_at, set when the underlying
order is cancelled before its batch was committed; the allocation row is
kept (not deleted) so batch history stays truthful about what was once
pooled in.

purchasing_batch_events.valid_event_type gains 'allocation_voided'. Its
existing CHECK constraint is dropped and recreated rather than altered in
place -- Postgres has no ALTER CHECK. While doing so this also fixes a
naming bug from the prior migration: op.create_table's CheckConstraint
was given an already-prefixed name ("ck_purchasing_batch_events_..."),
and since Alembic's naming_convention ("ck": "ck_%(table_name)s_%(constraint_name)s")
substitutes the given name into %(constraint_name)s regardless of whether
it looks pre-prefixed, that produced a doubled, 63-char-truncated,
hash-suffixed name that isn't reliably reproducible by name alone. The
drop step below looks the constraint up dynamically (by table + column
reference) instead of hardcoding either the broken or fixed name, so
upgrade/downgrade stay correct regardless of which form is currently
present. The sibling tables (purchasing_batches, purchasing_batch_allocations)
have the same cosmetic issue on their own CHECK constraints but are left
alone here -- harmless (the constraints still enforce correctly) and out
of scope for this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0031"
down_revision: str | None = "20260719_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CANCELLATIONS = "orders_cancellations"
_ALLOCATIONS = "purchasing_batch_allocations"
_EVENTS = "purchasing_batch_events"


def _drop_event_type_check_constraint() -> None:
    """Find and drop whatever CHECK constraint currently enforces
    event_type on purchasing_batch_events, whatever its name happens to
    be. Never a no-op silently: raises if none is found, since both
    upgrade() and downgrade() always expect exactly one to be present
    before they run (op.create_table's original, or this migration's own
    fixed-name recreation)."""
    op.execute(
        """
        DO $$
        DECLARE
            existing_name text;
        BEGIN
            SELECT conname INTO existing_name
            FROM pg_constraint
            WHERE conrelid = 'purchasing_batch_events'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%event_type%';
            IF existing_name IS NULL THEN
                RAISE EXCEPTION 'no event_type CHECK constraint found on purchasing_batch_events';
            END IF;
            EXECUTE format(
                'ALTER TABLE purchasing_batch_events DROP CONSTRAINT %I', existing_name
            );
        END $$;
        """
    )


def upgrade() -> None:
    op.add_column(_ALLOCATIONS, sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))

    _drop_event_type_check_constraint()
    op.create_check_constraint(
        "valid_event_type",
        _EVENTS,
        "event_type IN ('opened','threshold_reached','committed','cancelled',"
        "'allocation_voided')",
    )

    op.create_table(
        _CANCELLATIONS,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "order_id", sa.Uuid(), sa.ForeignKey("orders_orders.id"), nullable=False
        ),
        sa.Column(
            "cancelled_by_customer_identity_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "order_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("refund_amount_irr", sa.Integer(), nullable=False),
        sa.Column("refund_status", sa.String(20), nullable=False, server_default="owed"),
        sa.Column("refund_attested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "refund_attested_by_operator_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.Column(
            "refund_evidence_file_id",
            sa.Uuid(),
            sa.ForeignKey("trust_evidence_files.id"),
            nullable=True,
        ),
        sa.Column("refund_reference", sa.String(300), nullable=True),
        sa.UniqueConstraint("order_id", name="one_cancellation_per_order"),
    )
    op.create_index("ix_orders_cancellations_order_id", _CANCELLATIONS, ["order_id"])
    op.create_check_constraint(
        "valid_refund_status",
        _CANCELLATIONS,
        "refund_status IN ('owed','operator_attested')",
    )
    op.create_check_constraint(
        "positive_refund_amount", _CANCELLATIONS, "refund_amount_irr > 0"
    )


def downgrade() -> None:
    op.drop_table(_CANCELLATIONS)
    # Restores the constraint's *behavior* (no 'allocation_voided'), using
    # the same short-name form upgrade() used -- not the original ugly
    # double-prefixed hash name, which would just reintroduce the naming
    # bug this migration fixed.
    #
    # Any purchasing_batch_events rows already recording 'allocation_voided'
    # (written by a real customer cancellation while this migration was
    # applied) would violate the narrower CHECK being restored below, so
    # they're deleted first rather than recoded to an existing value --
    # 'cancelled' means the *batch* was cancelled, a different fact, and
    # relabeling would misrepresent history rather than just losing an
    # audit-trail entry. This mirrors dropping orders_cancellations above:
    # downgrade does not try to preserve every fact recorded while this
    # migration was applied, only the schema shape from before it.
    op.execute(f"DELETE FROM {_EVENTS} WHERE event_type = 'allocation_voided'")
    _drop_event_type_check_constraint()
    op.create_check_constraint(
        "valid_event_type",
        _EVENTS,
        "event_type IN ('opened','threshold_reached','committed','cancelled')",
    )
    op.drop_column(_ALLOCATIONS, "voided_at")
