"""Add 'superseded' refund status for shelf-life exceptions (correctness fix).

Revision ID: 20260720_0043
Revises: 20260720_0042

Workstream 7 (20260720_0038) allowed re-proposing a shelf-life exception
after the prior one was declined or expired, but left two real defects
found auditing the actual accept path against that change, not assumed:

1. accept_shelf_life_exception creates real SourcedUnitEvidence for the
   line (unblocking delivery projection, per this module's own docstring)
   but never cleared `order_line.excluded_from_delivery_at`, which the
   FIRST (declined/expired) proposal had already set. project_delivered_order
   checks that flag before it ever looks at evidence, so a line accepted
   via a *second* proposal stayed permanently excluded from delivery
   despite having real, accepted evidence.
2. The first proposal's full-line refund (`refund_status='owed'`) was
   never superseded when a later proposal for the same line was accepted
   -- both a full-line refund and the accepted line's product could be
   paid out/delivered together, a real double-liability, not merely a
   bookkeeping inconsistency.

This migration only widens `refund_status`'s CHECK constraint to include
'superseded' (a terminal, non-payable state distinct from 'owed' --
refund_attestation.py's attest_refund already rejects anything other than
exactly 'owed', so a superseded row can never be attested by construction,
not by a new runtime check). The paired app-code change
(app/modules/orders/shelf_life_exceptions.py) sets it.

Downgrade is safe only if no row is currently 'superseded' -- fails
closed with a clear error otherwise, matching this program's migration
safety requirements, rather than silently coercing data to fit the old
constraint.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260720_0043"
down_revision: str | None = "20260720_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "orders_shelf_life_exceptions"


def upgrade() -> None:
    op.drop_constraint("valid_refund_status", _TABLE, type_="check")
    op.create_check_constraint(
        "valid_refund_status",
        _TABLE,
        "refund_status IN ('not_applicable','owed','operator_attested','superseded')",
    )


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
            superseded_count integer;
        BEGIN
            SELECT count(*) INTO superseded_count FROM {_TABLE} WHERE refund_status = 'superseded';
            IF superseded_count > 0 THEN
                RAISE EXCEPTION
                    'cannot downgrade 20260720_0043: % row(s) have refund_status=''superseded'', '
                    'which the restored constraint cannot represent -- resolve them first',
                    superseded_count;
            END IF;
        END $$;
        """
    )
    op.drop_constraint("valid_refund_status", _TABLE, type_="check")
    op.create_check_constraint(
        "valid_refund_status",
        _TABLE,
        "refund_status IN ('not_applicable','owed','operator_attested')",
    )
