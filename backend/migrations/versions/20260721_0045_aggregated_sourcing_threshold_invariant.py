"""Enforce the aggregated-sourcing threshold invariant at the database (Workstream 7).

Revision ID: 20260721_0045
Revises: 20260720_0044

app.modules.purchasing.service._find_or_open_batch already refuses to
open an aggregated batch with no default_batch_threshold_quantity
configured (raising PurchasingError rather than guessing a value), and
both offer-creation and sourcing-config routes, plus
CheckoutService.create_order_uncommitted's own preflight, now reject
the same misconfiguration earlier -- at creation time and at checkout,
respectively, instead of only at payment-verification time. Those are
all application-layer enforcement; this migration adds the same
invariant as a real CHECK constraint, so it holds regardless of which
code path (or a future one) writes to catalog_offers, matching this
program's "enforced at schema/API/DB" requirement for this fact rather
than only at the routes we happened to touch.

Individual-route offers need no threshold at all (the purchasing
service always opens their batch with a hardcoded threshold of 1,
never a configurable value), so the constraint only fires for
sourcing_route='aggregated':
CHECK (sourcing_route <> 'aggregated' OR default_batch_threshold_quantity IS NOT NULL).

Reconfirming this against test_migration_20260717_0025_downgrade.py (an
existing test exercising a real downgrade below this point, then
re-upgrading) surfaced the actual shape "existing invalid rows" takes
in practice: 20260719_0029 added sourcing_route with
server_default='aggregated' and default_batch_threshold_quantity as a
bare nullable column with no backfill -- so every row that existed
*before* 0029 first ran (or that runs through a downgrade past 0029
and back up again) is backfilled into exactly the state this
constraint would reject, through no operator action at all. That is
categorically different from a row an operator affirmatively set to
sourcing_route='aggregated' without configuring a threshold: it is
0029's own unconfigured-backfill default, not a decision anyone made,
so reclassifying it to sourcing_route='individual' invents nothing --
it is the same "no real aggregation benefit configured" fact this
constraint exists to enforce, made truthful by construction rather
than left in a state that can never actually open a batch. This
migration performs exactly that reclassification before adding the
constraint (logged via row count, not silent), rather than failing
closed on data whose "violation" is 0029's own default, not a real
operator decision needing review.
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260721_0045"
down_revision: str | None = "20260720_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "catalog_offers"
_CONSTRAINT = "aggregated_route_requires_threshold"


def upgrade() -> None:
    connection = op.get_bind()
    reclassified = connection.execute(
        text(
            f"UPDATE {_TABLE} SET sourcing_route = 'individual' "
            "WHERE sourcing_route = 'aggregated' AND default_batch_threshold_quantity IS NULL"
        )
    ).rowcount
    if reclassified:
        print(  # noqa: T201 -- alembic migration progress output, not application logging
            f"20260721_0045: reclassified {reclassified} row(s) in {_TABLE} from "
            "sourcing_route='aggregated' (with no default_batch_threshold_quantity -- "
            "20260719_0029's own unconfigured-backfill default, not an operator "
            "decision) to sourcing_route='individual', the truthful representation "
            "of 'no aggregation actually configured'."
        )
    op.create_check_constraint(
        _CONSTRAINT,
        _TABLE,
        "sourcing_route <> 'aggregated' OR default_batch_threshold_quantity IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
