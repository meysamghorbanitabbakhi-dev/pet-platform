"""Add algorithm_version/request_hash to food estimates (Workstream 8).

Revision ID: 20260720_0039
Revises: 20260720_0038

InventoryService.open_and_estimate's replay-safety check previously
compared only 4 fields (remaining_quantity_grams, remaining_low_grams,
remaining_high_grams, remaining_input_mode) -- it silently ignored
feeding_context and daily_portion_grams entirely, so a genuinely
different request (e.g. a different feeding_context) landing on the
same remaining-quantity facts as an existing active estimate would be
wrongly treated as a safe replay and returned the stale estimate
instead of being rejected in favor of the correction endpoint.

Both new columns are nullable and NOT backfilled with a computed value
for existing rows: request_hash cannot be honestly reconstructed for
them (their original daily_portion_grams was never captured in
`provenance`, only inferable after this migration's paired app-code
change), and fabricating one would be worse than leaving it absent --
open_and_estimate treats a NULL request_hash as "can never match a
replay," which is the correct, safe behavior for a row that predates
this check. algorithm_version is backfilled with the explicit sentinel
'legacy_unversioned' (a true fact -- these rows really do predate
algorithm versioning) rather than assuming they came from the version
that happens to be live today.

Downgrade is lossless: both columns are purely additive.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0039"
down_revision: str | None = "20260720_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "food_estimation_estimates"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("algorithm_version", sa.String(length=20), nullable=True))
    op.add_column(_TABLE, sa.Column("request_hash", sa.String(length=64), nullable=True))
    op.execute(
        f"UPDATE {_TABLE} SET algorithm_version = 'legacy_unversioned' "
        "WHERE algorithm_version IS NULL"
    )


def downgrade() -> None:
    op.drop_column(_TABLE, "request_hash")
    op.drop_column(_TABLE, "algorithm_version")
