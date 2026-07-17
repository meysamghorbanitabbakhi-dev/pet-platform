"""price_intelligence: external price sources, products, observations, matches, runs, fx

Revision ID: 20260716_0022
Revises: 20260716_0021
Create Date: 2026-07-16 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260716_0022"
down_revision: str | None = "20260716_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ExternalPriceSource
    op.create_table(
        "price_intelligence_external_price_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("default_currency", sa.String(3), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="marketplace"),
        sa.Column("collection_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("robots_status", sa.String(32), nullable=False, server_default="unchecked"),
        sa.Column("robots_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terms_status", sa.String(32), nullable=False, server_default="unchecked"),
        sa.Column("terms_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terms_evidence_url", sa.String(1000), nullable=True),
        sa.Column("last_successful_collection_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "robots_status IN ('unchecked','allowed','disallowed','partial','failed')",
            name="valid_robots_status",
        ),
        sa.CheckConstraint(
            "terms_status IN ('unchecked','accepted','rejected','failed')",
            name="valid_terms_status",
        ),
        sa.CheckConstraint(
            "source_type IN ('marketplace','retailer','aggregator')",
            name="valid_source_type",
        ),
        sa.CheckConstraint("length(code) >= 2 AND length(code) <= 64", name="valid_code_length"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ExternalSeller
    op.create_table(
        "price_intelligence_external_sellers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("price_intelligence_external_price_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_seller_id", sa.String(200), nullable=True),
        sa.Column("seller_name", sa.String(300), nullable=False),
        sa.Column("seller_url", sa.String(1000), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "external_seller_id", name="uq_external_sellers_source_ext_id"),
        sa.UniqueConstraint("source_id", "seller_name", name="uq_external_sellers_source_name"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_sellers_source_id", "price_intelligence_external_sellers", ["source_id"])

    # ExternalProduct
    op.create_table(
        "price_intelligence_external_products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("price_intelligence_external_price_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_product_id", sa.String(200), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("source_title", sa.String(500), nullable=False),
        sa.Column("brand_name", sa.String(200), nullable=False, server_default="Royal Canin"),
        sa.Column("species", sa.String(16), nullable=True),
        sa.Column("food_type", sa.String(16), nullable=True),
        sa.Column("life_stage", sa.String(16), nullable=True),
        sa.Column("product_line", sa.String(200), nullable=True),
        sa.Column("formula_name", sa.String(300), nullable=True),
        sa.Column("veterinary_diet", sa.Boolean(), nullable=True),
        sa.Column("declared_pack_count", sa.Integer(), nullable=True),
        sa.Column("declared_unit_weight_g", sa.Integer(), nullable=True),
        sa.Column("declared_total_weight_g", sa.Integer(), nullable=True),
        sa.Column("raw_pack_text", sa.String(200), nullable=True),
        sa.Column("availability", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column(
            "seller_id",
            sa.Uuid(),
            sa.ForeignKey("price_intelligence_external_sellers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint("source_id", "external_product_id", name="uq_extprod_source_extid"),
        sa.CheckConstraint("species IN ('dog','cat','other') OR species IS NULL", name="valid_species"),
        sa.CheckConstraint("food_type IN ('dry','wet','treat','other') OR food_type IS NULL", name="valid_food_type"),
        sa.CheckConstraint(
            "life_stage IN ('puppy','kitten','adult','senior','all_stages') OR life_stage IS NULL",
            name="valid_life_stage",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_products_source_id", "price_intelligence_external_products", ["source_id"])
    op.create_index("ix_external_products_last_seen_at", "price_intelligence_external_products", ["last_seen_at"])

    # ExternalProductMatch
    op.create_table(
        "price_intelligence_external_product_matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "external_product_id",
            sa.Uuid(),
            sa.ForeignKey("price_intelligence_external_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "canonical_product_id",
            sa.Uuid(),
            sa.ForeignKey("catalog_products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "canonical_variant_id",
            sa.Uuid(),
            sa.ForeignKey("catalog_offers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("canonical_ean", sa.String(32), nullable=True),
        sa.Column("match_method", sa.String(32), nullable=False),
        sa.Column("match_confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("match_status", sa.String(32), nullable=False, server_default="unmatched"),
        sa.Column("match_reasons_json", sa.JSON(), nullable=True),
        sa.Column(
            "reviewed_by",
            sa.Uuid(),
            sa.ForeignKey("identity_auth_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "match_method IN ('ean','exact_formula_weight','normalized_attributes','manual')",
            name="valid_match_method",
        ),
        sa.CheckConstraint(
            "match_status IN ('unmatched','suggested','needs_review','approved','rejected')",
            name="valid_match_status",
        ),
        sa.CheckConstraint("match_confidence BETWEEN 0 AND 1", name="valid_match_confidence"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_external_product_matches_external_product_id",
        "price_intelligence_external_product_matches",
        ["external_product_id"],
    )
    op.create_index(
        "ix_external_product_matches_canonical_product_id",
        "price_intelligence_external_product_matches",
        ["canonical_product_id"],
    )
    op.create_index(
        "ix_external_product_matches_status",
        "price_intelligence_external_product_matches",
        ["match_status"],
    )

    # ExternalCollectionRun
    op.create_table(
        "price_intelligence_external_collection_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("price_intelligence_external_price_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("pages_requested", sa.Integer(), nullable=True),
        sa.Column("pages_succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prices_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary_json", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed','cancelled')",
            name="valid_collection_run_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_collection_runs_source_id_started",
        "price_intelligence_external_collection_runs",
        ["source_id", "started_at"],
    )

    # ExternalPriceObservation
    op.create_table(
        "price_intelligence_external_price_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "external_product_id",
            sa.Uuid(),
            sa.ForeignKey("price_intelligence_external_products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "seller_id",
            sa.Uuid(),
            sa.ForeignKey("price_intelligence_external_sellers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("currency", sa.String(3), nullable=False, server_default="AMD"),
        sa.Column("price_minor", sa.BigInteger(), nullable=False),
        sa.Column("compare_at_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("pack_count", sa.Integer(), nullable=True),
        sa.Column("unit_weight_g", sa.Integer(), nullable=True),
        sa.Column("total_weight_g", sa.Integer(), nullable=True),
        sa.Column("unit_price_per_kg_minor", sa.BigInteger(), nullable=True),
        sa.Column("availability", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "collection_run_id",
            sa.Uuid(),
            sa.ForeignKey(
                "price_intelligence_external_collection_runs.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("raw_price_text", sa.String(200), nullable=True),
        sa.CheckConstraint(
            "availability IN ('unknown','available','unavailable','preorder')",
            name="valid_observation_availability",
        ),
        sa.CheckConstraint("price_minor >= 0", name="valid_price_minor"),
        sa.CheckConstraint(
            "unit_price_per_kg_minor IS NULL OR unit_price_per_kg_minor >= 0",
            name="valid_unit_price_per_kg_minor",
        ),
        sa.UniqueConstraint(
            "external_product_id",
            "seller_id",
            "observed_at",
            name="uq_observation_prod_seller_ts",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_observation_prod_seller_observed",
        "price_intelligence_external_price_observations",
        ["external_product_id", "seller_id", "observed_at"],
    )
    op.create_index(
        "ix_observation_collection_run_id",
        "price_intelligence_external_price_observations",
        ["collection_run_id"],
    )
    op.create_index(
        "ix_observation_external_product_id",
        "price_intelligence_external_price_observations",
        ["external_product_id"],
    )

    # ExchangeRateSnapshot
    op.create_table(
        "price_intelligence_exchange_rate_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exchange_rates_base_quote_observed",
        "price_intelligence_exchange_rate_snapshots",
        ["base_currency", "quote_currency", "observed_at"],
    )


def downgrade() -> None:
    op.drop_table("price_intelligence_exchange_rate_snapshots")
    op.drop_table("price_intelligence_external_price_observations")
    op.drop_table("price_intelligence_external_collection_runs")
    op.drop_table("price_intelligence_external_product_matches")
    op.drop_table("price_intelligence_external_products")
    op.drop_table("price_intelligence_external_sellers")
    op.drop_table("price_intelligence_external_price_sources")
