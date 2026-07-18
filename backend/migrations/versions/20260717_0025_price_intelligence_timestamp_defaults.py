"""price_intelligence: repair timestamp defaults and match_method constraint

Revision ID: 20260717_0025
Revises: 20260716_0024
Create Date: 2026-07-17 13:00:00.000000

Two schema/domain-model mismatches in the price_intelligence tables:

1. created_at/updated_at (migration 20260716_0022 and the 20260716_0024
   repair) were declared NOT NULL without a server_default, unlike every
   other TimestampMixin-backed table in this schema. The ORM's
   TimestampMixin relies on server_default=func.now() to populate these
   columns; without it in the DDL, any insert that does not explicitly set
   both timestamps violates the NOT NULL constraint.

2. The valid_match_method CHECK constraint on
   price_intelligence_external_product_matches omits 'unmatched', even
   though app.integrations.price_intelligence.matcher.MatchMethod.UNMATCHED
   is the value the matching pipeline legitimately writes for every
   external product with no canonical match -- the normal, common outcome
   for a newly-discovered product. Without 'unmatched' in the allowed set,
   ingesting any unmatched product violates the CHECK constraint and
   aborts the whole collection run instead of degrading gracefully.

Existing rows are unaffected: ALTER COLUMN ... SET DEFAULT only applies to
future inserts, and the constraint is only widened, never narrowed.

Downgrade safety: recreating the narrower CHECK constraint on downgrade would
make Postgres validate it against every existing row, and any row already
written with match_method='unmatched' (the normal, common matcher outcome --
see above) would fail that validation and abort the downgrade with a raw,
unactionable constraint-violation error. 'unmatched' has no correct narrower
equivalent to remap it to -- it is not a wrong value, it is a true statement
that no canonical match was found, and silently rewriting it to e.g. 'manual'
would misstate those rows' provenance. So downgrade() checks for existing
'unmatched' rows first and fails early with an explicit, actionable error
instead of letting the constraint creation fail unpredictably; the operator
must then decide (and execute) whether to delete the affected derived match
rows before downgrading, or stay on this migration's wider constraint.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0025"
down_revision: str | None = "20260716_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = [
    "price_intelligence_external_price_sources",
    "price_intelligence_external_sellers",
    "price_intelligence_external_products",
    "price_intelligence_external_product_matches",
    "price_intelligence_external_collection_runs",
    "price_intelligence_external_price_observations",
    "price_intelligence_exchange_rate_snapshots",
    "price_intelligence_external_product_match_reviews",
]

_MATCHES_TABLE = "price_intelligence_external_product_matches"


def upgrade() -> None:
    for table in _TABLES:
        op.alter_column(table, "created_at", server_default=sa.text("now()"))
        op.alter_column(table, "updated_at", server_default=sa.text("now()"))

    op.drop_constraint("valid_match_method", _MATCHES_TABLE, type_="check")
    op.create_check_constraint(
        "valid_match_method",
        _MATCHES_TABLE,
        "match_method IN "
        "('unmatched','ean','exact_formula_weight','normalized_attributes','manual')",
    )


def downgrade() -> None:
    bind = op.get_bind()
    unmatched_count = bind.execute(
        sa.text(f"SELECT COUNT(*) FROM {_MATCHES_TABLE} WHERE match_method = 'unmatched'")
    ).scalar_one()
    if unmatched_count:
        raise RuntimeError(
            f"Cannot downgrade past 20260717_0025: {unmatched_count} row(s) in "
            f"{_MATCHES_TABLE} have match_method='unmatched', which the narrower "
            "pre-migration constraint does not allow. 'unmatched' has no correct "
            "narrower equivalent (it is a true statement, not an error), so this "
            "downgrade will not remap it automatically. Before downgrading, either "
            "delete the affected rows (if they are safe to discard) or stay on this "
            "migration's wider constraint."
        )

    op.drop_constraint("valid_match_method", _MATCHES_TABLE, type_="check")
    op.create_check_constraint(
        "valid_match_method",
        _MATCHES_TABLE,
        "match_method IN ('ean','exact_formula_weight','normalized_attributes','manual')",
    )

    for table in _TABLES:
        op.alter_column(table, "created_at", server_default=None)
        op.alter_column(table, "updated_at", server_default=None)
