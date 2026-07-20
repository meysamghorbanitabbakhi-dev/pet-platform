"""Allow re-proposing a shelf-life exception; require a positive discount (Workstream 7).

Revision ID: 20260720_0038
Revises: 20260720_0037

Two related tightenings found auditing ADR-007 against the gap-closure
mission brief:

1. ADR-007 deliberately made `one_exception_per_order_line` a hard,
   permanent one-shot constraint and explicitly flagged the consequence:
   "a mistaken proposal (wrong discount, wrong date) cannot be corrected
   in place ... nothing else can be proposed for that line automatically
   ... A future workstream would need to add an explicit re-open/
   re-propose path if this turns out to matter operationally." This is
   that workstream. Replaces the always-on unique constraint with a
   partial unique index that only applies while a proposal is still
   'proposed' (live) -- at most one active proposal per order line at a
   time, exactly as before, but a resolved (declined/expired) proposal no
   longer permanently blocks a revised one. 'accepted' is not part of the
   partial index's predicate either, but propose_shelf_life_exception's
   own already_sourced check (SourcedUnitEvidence exists once accepted)
   independently prevents a new proposal for an already-accepted line, so
   this does not reopen that case.

2. `additional_discount_irr >= 0` allowed a $0-compensation exception --
   asking a customer to accept a product that falls short of the
   guarantee they paid for with nothing in return. Tightened to `> 0`.
   No backfill is needed: every existing row was written by
   propose_shelf_life_exception, whose Pydantic request body already
   required `ge=0`, but the DB constraint is the one being tightened
   here, not application data assumed to already satisfy it -- if any
   row violates the new constraint this migration fails closed rather
   than silently succeeding.

Downgrade of the unique index is lossless only if at most one exception
row exists per order line at the time it runs (i.e. no line has actually
used the new re-proposal path yet) -- it fails closed with a clear error
rather than silently picking one row to keep, matching this program's
migration safety requirements. Downgrade of the discount constraint is
always safe (widening).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260720_0038"
down_revision: str | None = "20260720_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "orders_shelf_life_exceptions"


def upgrade() -> None:
    op.drop_constraint("one_exception_per_order_line", _TABLE, type_="unique")
    op.create_index(
        "uq_shelf_life_exceptions_one_active_per_order_line",
        _TABLE,
        ["order_line_id"],
        unique=True,
        postgresql_where="status = 'proposed'",
    )
    op.drop_constraint("nonnegative_discount", _TABLE, type_="check")
    op.create_check_constraint("positive_discount", _TABLE, "additional_discount_irr > 0")


def downgrade() -> None:
    op.drop_constraint("positive_discount", _TABLE, type_="check")
    op.create_check_constraint("nonnegative_discount", _TABLE, "additional_discount_irr >= 0")
    op.execute(
        f"""
        DO $$
        DECLARE
            duplicate_count integer;
        BEGIN
            SELECT count(*) INTO duplicate_count FROM (
                SELECT order_line_id FROM {_TABLE}
                GROUP BY order_line_id HAVING count(*) > 1
            ) AS duplicates;
            IF duplicate_count > 0 THEN
                RAISE EXCEPTION
                    'cannot downgrade 20260720_0038: % order line(s) have more than one '
                    'shelf-life exception row, which the restored one_exception_per_order_line '
                    'constraint cannot represent -- resolve or archive the extra rows first',
                    duplicate_count;
            END IF;
        END $$;
        """
    )
    op.drop_index("uq_shelf_life_exceptions_one_active_per_order_line", _TABLE)
    op.create_unique_constraint("one_exception_per_order_line", _TABLE, ["order_line_id"])
