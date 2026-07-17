"""price_intelligence repair: observation idempotency, FX numeric, review audit

Revision ID: 20260716_0024
Revises: 20260716_0023
Create Date: 2026-07-17 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0024"
down_revision: str | None = "20260716_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "price_intelligence_external_price_observations",
        sa.Column("currency_exponent", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "price_intelligence_external_price_observations",
        sa.Column("ingestion_key", sa.String(length=128), nullable=True),
    )
    op.execute(
        """
        UPDATE price_intelligence_external_price_observations
        SET ingestion_key = md5(
            external_product_id::text || ':' || coalesce(seller_id::text, 'no-seller') || ':' ||
            observed_at::text || ':' || content_hash
        )
        WHERE ingestion_key IS NULL
        """
    )
    op.alter_column(
        "price_intelligence_external_price_observations",
        "ingestion_key",
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_observation_ingestion_key",
        "price_intelligence_external_price_observations",
        ["ingestion_key"],
    )
    op.alter_column(
        "price_intelligence_external_products",
        "raw_payload_json",
        type_=postgresql.JSONB(),
        existing_type=sa.JSON(),
        postgresql_using="raw_payload_json::jsonb",
    )
    op.alter_column(
        "price_intelligence_external_product_matches",
        "match_reasons_json",
        type_=postgresql.JSONB(),
        existing_type=sa.JSON(),
        postgresql_using="match_reasons_json::jsonb",
    )
    op.alter_column(
        "price_intelligence_external_collection_runs",
        "error_summary_json",
        type_=postgresql.JSONB(),
        existing_type=sa.JSON(),
        postgresql_using="error_summary_json::jsonb",
    )
    op.create_check_constraint(
        "valid_currency_exponent",
        "price_intelligence_external_price_observations",
        "currency_exponent >= 0 AND currency_exponent <= 6",
    )
    op.create_check_constraint(
        "valid_observation_currency",
        "price_intelligence_external_price_observations",
        "currency ~ '^[A-Z]{3}$'",
    )
    op.drop_constraint(
        "valid_price_minor",
        "price_intelligence_external_price_observations",
        type_="check",
    )
    op.create_check_constraint(
        "valid_price_minor",
        "price_intelligence_external_price_observations",
        "price_minor > 0",
    )
    op.alter_column(
        "price_intelligence_exchange_rate_snapshots",
        "rate",
        type_=sa.Numeric(24, 12),
        existing_type=sa.String(length=64),
        postgresql_using="rate::numeric",
    )
    op.create_check_constraint(
        "valid_exchange_rate",
        "price_intelligence_exchange_rate_snapshots",
        "rate > 0",
    )
    op.create_unique_constraint(
        "uq_external_product_current_match",
        "price_intelligence_external_product_matches",
        ["external_product_id"],
    )
    op.create_table(
        "price_intelligence_external_product_match_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("operator_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("previous_canonical_product_id", sa.String(length=36), nullable=True),
        sa.Column("new_canonical_product_id", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('approved','rejected','remapped')",
            name="valid_match_review_decision",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["price_intelligence_external_product_matches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["operator_id"],
            ["identity_auth_identities.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_match_reviews_match_id",
        "price_intelligence_external_product_match_reviews",
        ["match_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_match_reviews_match_id",
        table_name="price_intelligence_external_product_match_reviews",
    )
    op.drop_table("price_intelligence_external_product_match_reviews")
    op.drop_constraint(
        "uq_external_product_current_match",
        "price_intelligence_external_product_matches",
        type_="unique",
    )
    op.drop_constraint(
        "valid_exchange_rate",
        "price_intelligence_exchange_rate_snapshots",
        type_="check",
    )
    op.alter_column(
        "price_intelligence_exchange_rate_snapshots",
        "rate",
        type_=sa.String(length=64),
        existing_type=postgresql.NUMERIC(precision=24, scale=12),
        postgresql_using="rate::text",
    )
    op.drop_constraint(
        "valid_price_minor",
        "price_intelligence_external_price_observations",
        type_="check",
    )
    op.create_check_constraint(
        "valid_price_minor",
        "price_intelligence_external_price_observations",
        "price_minor >= 0",
    )
    op.drop_constraint(
        "valid_observation_currency",
        "price_intelligence_external_price_observations",
        type_="check",
    )
    op.drop_constraint(
        "valid_currency_exponent",
        "price_intelligence_external_price_observations",
        type_="check",
    )
    op.drop_constraint(
        "uq_observation_ingestion_key",
        "price_intelligence_external_price_observations",
        type_="unique",
    )
    op.alter_column(
        "price_intelligence_external_collection_runs",
        "error_summary_json",
        type_=sa.JSON(),
        existing_type=postgresql.JSONB(),
        postgresql_using="error_summary_json::json",
    )
    op.alter_column(
        "price_intelligence_external_product_matches",
        "match_reasons_json",
        type_=sa.JSON(),
        existing_type=postgresql.JSONB(),
        postgresql_using="match_reasons_json::json",
    )
    op.alter_column(
        "price_intelligence_external_products",
        "raw_payload_json",
        type_=sa.JSON(),
        existing_type=postgresql.JSONB(),
        postgresql_using="raw_payload_json::json",
    )
    op.drop_column("price_intelligence_external_price_observations", "ingestion_key")
    op.drop_column("price_intelligence_external_price_observations", "currency_exponent")
