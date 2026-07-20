"""Fix household-creation RETURNING vs RLS SELECT-policy conflict (Workstream 9).

Revision ID: 20260720_0042
Revises: 20260720_0041

Testing 20260720_0041's households_households policies against the real
create_household route (POST /pet-life/households) surfaced a genuine
Postgres RLS interaction this program's test suite exists to catch:
Postgres evaluates an INSERT ... RETURNING clause's output against the
table's SELECT policy, not just the INSERT policy's WITH CHECK. SQLAlchemy
issues RETURNING automatically for any row with a server_default column
(created_at/updated_at, via TimestampMixin) so it can populate the
in-memory object -- unavoidable without disabling that project-wide.

households_households_select requires id = ANY(app_household_ids()), and
a brand-new household is, by construction, not yet in the creator's
app_household_ids() (that snapshot was computed at the start of the
request, before this INSERT). The HouseholdMembership row that would
establish membership is added immediately afterward in the same route,
but does not exist yet at the moment this specific INSERT's RETURNING is
evaluated -- so no live membership check could help either, only a fact
available at INSERT time itself.

Adds `created_by_identity_id` (nullable; never backfilled for existing
rows -- a household can have several members, and no prior row recorded
who acted first, so "who created this" cannot be honestly reconstructed
for them) and extends the SELECT/UPDATE/DELETE policies with an
`OR created_by_identity_id = app_identity_id()` fallback, mirroring
20260720_0041's identical fix for households_memberships' own INSERT
bootstrap case.

Downgrade drops the fallback clause from each policy and the column;
lossless (the column is purely additive audit data, not referenced by
any other constraint).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0042"
down_revision: str | None = "20260720_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "households_households"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(
            "created_by_identity_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
    )

    op.execute(f"DROP POLICY households_households_select ON {_TABLE}")
    op.execute(
        f"CREATE POLICY households_households_select ON {_TABLE} "
        "FOR SELECT USING ("
        "  app_is_operator()"
        "  OR id = ANY(app_household_ids())"
        "  OR created_by_identity_id = app_identity_id()"
        ")"
    )

    op.execute(f"DROP POLICY households_households_update ON {_TABLE}")
    op.execute(
        f"CREATE POLICY households_households_update ON {_TABLE} "
        "FOR UPDATE USING ("
        "  app_is_operator()"
        "  OR id = ANY(app_household_ids())"
        "  OR created_by_identity_id = app_identity_id()"
        ") WITH CHECK ("
        "  app_is_operator()"
        "  OR id = ANY(app_household_ids())"
        "  OR created_by_identity_id = app_identity_id()"
        ")"
    )

    op.execute(f"DROP POLICY households_households_delete ON {_TABLE}")
    op.execute(
        f"CREATE POLICY households_households_delete ON {_TABLE} "
        "FOR DELETE USING ("
        "  app_is_operator()"
        "  OR id = ANY(app_household_ids())"
        "  OR created_by_identity_id = app_identity_id()"
        ")"
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY households_households_delete ON {_TABLE}")
    op.execute(
        f"CREATE POLICY households_households_delete ON {_TABLE} "
        "FOR DELETE USING (app_is_operator() OR id = ANY(app_household_ids()))"
    )

    op.execute(f"DROP POLICY households_households_update ON {_TABLE}")
    op.execute(
        f"CREATE POLICY households_households_update ON {_TABLE} "
        "FOR UPDATE USING (app_is_operator() OR id = ANY(app_household_ids())) "
        "WITH CHECK (app_is_operator() OR id = ANY(app_household_ids()))"
    )

    op.execute(f"DROP POLICY households_households_select ON {_TABLE}")
    op.execute(
        f"CREATE POLICY households_households_select ON {_TABLE} "
        "FOR SELECT USING (app_is_operator() OR id = ANY(app_household_ids()))"
    )

    op.drop_column(_TABLE, "created_by_identity_id")
