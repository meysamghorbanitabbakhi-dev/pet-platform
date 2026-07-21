"""Add a resolved-calculation-context hash to food estimates (Workstream 8/9).

Revision ID: 20260721_0046
Revises: 20260721_0045

FoodEstimate.request_hash exists purely for replay-safety
(open_and_estimate's "is this an exact repeat of the same request"
check) -- it is deliberately computed over the caller's *raw* submitted
daily_portion_grams, before feeding_context/consumption-assignment
resolution runs, so a request that happens to resolve to the same
derived number is not mistaken for a literal repeat, and a request that
changes an input is never masked as safe to replay.

That leaves no durable record of what the calculation actually *used*
once resolution has run: which specific ConsumptionAssignment rows
contributed to a derived daily_portion_grams, and what algorithm/schema
version and resolved (not merely requested) portion the stored
low_days/high_days actually came from. Two different assignment
configurations that happen to resolve to the same total portion would
be indistinguishable after the fact with request_hash alone -- which
matters for auditing a prediction against a real outcome, or explaining
to an operator why a specific estimate looks the way it does.

resolved_context_hash is that second, independent fact: nullable (nothing
here rewrites request_hash's existing rows, and a legacy row's original
resolution inputs were never captured, so backfilling would be a guess,
not a fact -- same reasoning 20260720_0039 already applied to
request_hash/algorithm_version).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_0046"
down_revision: str | None = "20260721_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "food_estimation_estimates"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("resolved_context_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column(_TABLE, "resolved_context_hash")
