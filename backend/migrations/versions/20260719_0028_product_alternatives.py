"""Operator-curated product alternatives (G5-SHOP-13).

Revision ID: 20260719_0028
Revises: 20260719_0027

Adds an explicit, directed, operator-curated product-to-product
substitutability domain -- catalog_product_alternatives -- instead of an
inferred matcher over product names/categories. Deliberately a new table
under app/modules/catalog, not a reuse of any price_intelligence match
table: those represent external-source-to-canonical-product matching for
pricing, an unrelated domain with different authorization and lifecycle
semantics.

New table only; no existing data affected, no backfill required.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0028"
down_revision: str | None = "20260719_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "catalog_product_alternatives"


def upgrade() -> None:
    op.create_table(
        _TABLE,
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
            "source_product_id",
            sa.Uuid(),
            sa.ForeignKey("catalog_products.id"),
            nullable=False,
        ),
        sa.Column(
            "alternative_product_id",
            sa.Uuid(),
            sa.ForeignKey("catalog_products.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="proposed"),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rationale_fa", sa.Text(), nullable=False),
        sa.Column("compatibility_notes_fa", sa.Text(), nullable=True),
        sa.Column(
            "proposed_by_operator_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=False,
        ),
        sa.Column(
            "approved_by_operator_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "retired_by_operator_id",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id"),
            nullable=True,
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source_product_id != alternative_product_id", name="no_self_alternative"
        ),
        sa.CheckConstraint(
            "status IN ('proposed','approved','retired')",
            name="ck_catalog_product_alternatives_valid_status",
        ),
        sa.UniqueConstraint(
            "source_product_id",
            "alternative_product_id",
            name="unique_product_alternative_pair",
        ),
    )
    op.create_index(
        "ix_catalog_product_alternatives_source_product_id",
        _TABLE,
        ["source_product_id"],
    )
    op.create_index(
        "ix_catalog_product_alternatives_alternative_product_id",
        _TABLE,
        ["alternative_product_id"],
    )
    # Public read path filters on (source_product_id, status); a composite
    # index serves that query directly instead of relying on the single-
    # column source index plus a filter scan.
    op.create_index(
        "ix_catalog_product_alternatives_source_status",
        _TABLE,
        ["source_product_id", "status", "rank"],
    )


def downgrade() -> None:
    op.drop_table(_TABLE)
