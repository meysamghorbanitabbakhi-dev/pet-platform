"""Price intelligence domain models.

Stores external price observations separately from our canonical catalog.
Never auto-imports products into the sellable catalog; external products
are for intelligence only.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExternalPriceSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A third-party price data source (e.g. Petmall Armenia)."""

    __tablename__ = "price_intelligence_external_price_sources"

    code: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="e.g. 'petsmall_am'"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="Human-readable name")
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    country_code: Mapped[str] = mapped_column(
        String(2), nullable=False, comment="ISO 3166-1 alpha-2"
    )
    default_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, comment="ISO 4217"
    )
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="marketplace",
        comment="marketplace | retailer | aggregator",
    )
    collection_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="Feature flag: gated by default"
    )
    # robots / TOS verification
    robots_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unchecked",
        comment="unchecked | allowed | disallowed | partial | failed",
    )
    robots_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terms_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unchecked",
        comment="unchecked | accepted | rejected | failed",
    )
    terms_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terms_evidence_url: Mapped[str | None] = mapped_column(String(1000))
    last_successful_collection_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    __table_args__ = (
        CheckConstraint(
            "robots_status IN "
            "('unchecked','allowed','disallowed','partial','failed')",
            name="valid_robots_status",
        ),
        CheckConstraint(
            "terms_status IN ('unchecked','accepted','rejected','failed')",
            name="valid_terms_status",
        ),
        CheckConstraint(
            "source_type IN ('marketplace','retailer','aggregator')",
            name="valid_source_type",
        ),
        CheckConstraint(
            "length(code) >= 2 AND length(code) <= 64", name="valid_code_length"
        ),
    )


class ExternalSeller(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A seller observed on an external source (e.g. RoCan Store on Petmall)."""

    __tablename__ = "price_intelligence_external_sellers"

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("price_intelligence_external_price_sources.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    external_seller_id: Mapped[str | None] = mapped_column(
        String(200),
        comment="Opaque seller handle as exposed by source (nullable for display-only sellers)",
    )
    seller_name: Mapped[str] = mapped_column(String(300), nullable=False)
    seller_url: Mapped[str | None] = mapped_column(String(1000))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # Unique on source + (external_seller_id OR seller_name)
        UniqueConstraint(
            "source_id",
            "external_seller_id",
            name="uq_external_sellers_source_ext_id",
        ),
        UniqueConstraint(
            "source_id", "seller_name", name="uq_external_sellers_source_name"
        ),
        Index("ix_external_sellers_source_id", "source_id"),
    )


class ExternalProduct(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    An external product listing observed on a source.
    Never imported into our canonical catalog automatically.
    """

    __tablename__ = "price_intelligence_external_products"
    __table_args__ = (
        UniqueConstraint("source_id", "external_product_id", name="uq_extprod_source_extid"),
        CheckConstraint(
            "species IN ('dog','cat','other') OR species IS NULL",
            name="valid_species",
        ),
        CheckConstraint(
            "food_type IN ('dry','wet','treat','other') OR food_type IS NULL",
            name="valid_food_type",
        ),
        CheckConstraint(
            "life_stage IN ('puppy','kitten','adult','senior','all_stages') OR life_stage IS NULL",
            name="valid_life_stage",
        ),
        CheckConstraint(
            "declared_pack_count IS NULL OR declared_pack_count > 0",
            name="positive_pack_count",
        ),
        CheckConstraint(
            "declared_unit_weight_g IS NULL OR declared_unit_weight_g > 0",
            name="positive_unit_weight",
        ),
        CheckConstraint(
            "declared_total_weight_g IS NULL OR declared_total_weight_g > 0",
            name="positive_total_weight",
        ),
        CheckConstraint(
            "availability IN ('unknown','available','unavailable','preorder')",
            name="valid_product_availability",
        ),
        CheckConstraint(
            "veterinary_diet IS NULL OR veterinary_diet IN (true, false)",
            name="valid_veterinary_diet",
        ),
        Index("ix_external_products_source_id", "source_id"),
        Index("ix_external_products_last_seen_at", "last_seen_at"),
    )

    # Linkage
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("price_intelligence_external_price_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_product_id: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Source-local SKU or slug"
    )

    # Source-provided metadata
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=False)
    source_title: Mapped[str] = mapped_column(String(500), nullable=False)
    brand_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="Royal Canin"
    )

    # Species / line classification
    species: Mapped[str | None] = mapped_column(String(16))
    food_type: Mapped[str | None] = mapped_column(String(16))
    life_stage: Mapped[str | None] = mapped_column(String(16))
    product_line: Mapped[str | None] = mapped_column(String(200))
    formula_name: Mapped[str | None] = mapped_column(String(300))
    veterinary_diet: Mapped[bool | None] = mapped_column(Boolean)

    # Packaging (all integers in grams; NULL if unknown)
    declared_pack_count: Mapped[int | None] = mapped_column(Integer)
    declared_unit_weight_g: Mapped[int | None] = mapped_column(Integer)
    declared_total_weight_g: Mapped[int | None] = mapped_column(Integer)
    raw_pack_text: Mapped[str | None] = mapped_column(String(200))

    # Status
    availability: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
        comment="unknown | available | unavailable | preorder",
    )
    seller_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("price_intelligence_external_sellers.id", ondelete="SET NULL"),
        index=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Raw structured payload (only when needed/permitted)
    raw_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class ExternalProductMatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A match (or non-match) between an external product and a canonical product.
    All non-EAN matches begin as suggested|needs_review; only EAN matches auto-approve.
    """

    __tablename__ = "price_intelligence_external_product_matches"
    __table_args__ = (
        CheckConstraint(
            "match_method IN "
            "('unmatched','ean','exact_formula_weight','normalized_attributes','manual')",
            name="valid_match_method",
        ),
        CheckConstraint(
            "match_status IN "
            "('unmatched','suggested','needs_review','approved','rejected')",
            name="valid_match_status",
        ),
        CheckConstraint(
            "match_confidence BETWEEN 0 AND 1",
            name="valid_match_confidence",
        ),
        Index("ix_external_product_matches_external_product_id", "external_product_id"),
        Index("ix_external_product_matches_canonical_product_id", "canonical_product_id"),
        Index("ix_external_product_matches_status", "match_status"),
        UniqueConstraint("external_product_id", name="uq_external_product_current_match"),
    )

    external_product_id: Mapped[UUID] = mapped_column(
        ForeignKey("price_intelligence_external_products.id", ondelete="CASCADE"),
        nullable=False,
    )
    canonical_product_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_products.id", ondelete="SET NULL"),
        index=True,
    )
    canonical_variant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_offers.id", ondelete="SET NULL"),
        index=True,
    )
    canonical_ean: Mapped[str | None] = mapped_column(String(32))

    match_method: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="ean | exact_formula_weight | normalized_attributes | manual",
    )
    match_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    match_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unmatched",
    )
    match_reasons_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, comment="Explains why match was made or why it failed"
    )

    # Operator review
    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExternalProductMatchReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable operator/audit history for match decisions."""

    __tablename__ = "price_intelligence_external_product_match_reviews"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved','rejected','remapped')",
            name="valid_match_review_decision",
        ),
        Index("ix_match_reviews_match_id", "match_id"),
    )

    match_id: Mapped[UUID] = mapped_column(
        ForeignKey("price_intelligence_external_product_matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(32))
    previous_canonical_product_id: Mapped[str | None] = mapped_column(String(36))
    new_canonical_product_id: Mapped[str | None] = mapped_column(String(36))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExternalPriceObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    An immutable price observation. Each change creates a new row;
    history is never overwritten.
    """

    __tablename__ = "price_intelligence_external_price_observations"
    __table_args__ = (
        CheckConstraint(
            "availability IN ('unknown','available','unavailable','preorder')",
            name="valid_observation_availability",
        ),
        CheckConstraint("price_minor > 0", name="valid_price_minor"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="valid_observation_currency"),
        CheckConstraint(
            "currency_exponent >= 0 AND currency_exponent <= 6",
            name="valid_currency_exponent",
        ),
        CheckConstraint(
            "unit_price_per_kg_minor IS NULL OR unit_price_per_kg_minor >= 0",
            name="valid_unit_price_per_kg_minor",
        ),
        # Dedup: same product+seller+observed_at OR same content_hash cannot repeat
        UniqueConstraint(
            "external_product_id",
            "seller_id",
            "observed_at",
            name="uq_observation_prod_seller_ts",
        ),
        Index(
            "ix_observation_prod_seller_observed",
            "external_product_id",
            "seller_id",
            "observed_at",
        ),
        Index("ix_observation_collection_run_id", "collection_run_id"),
        Index("ix_observation_external_product_id", "external_product_id"),
        UniqueConstraint("ingestion_key", name="uq_observation_ingestion_key"),
    )

    external_product_id: Mapped[UUID] = mapped_column(
        ForeignKey("price_intelligence_external_products.id", ondelete="CASCADE"),
        nullable=False,
    )
    seller_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("price_intelligence_external_sellers.id", ondelete="SET NULL"),
        index=True,
    )

    # Money — integer minor units (kopeks / luma / etc.)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="AMD", comment="ISO 4217"
    )
    currency_exponent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="source-currency minor units"
    )
    compare_at_price_minor: Mapped[int | None] = mapped_column(
        BigInteger, comment="Discounted-from price"
    )

    # Packaging snapshot at observation time
    pack_count: Mapped[int | None] = mapped_column(Integer)
    unit_weight_g: Mapped[int | None] = mapped_column(Integer)
    total_weight_g: Mapped[int | None] = mapped_column(Integer)

    # Derived only when pack_count + unit_weight_g are both set and non-zero
    unit_price_per_kg_minor: Mapped[int | None] = mapped_column(
        BigInteger, comment="price_minor * 1000 / total_weight_g, NULL if ambiguous"
    )

    availability: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    collection_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("price_intelligence_external_collection_runs.id", ondelete="SET NULL"),
        index=True,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="sha256 of raw payload for dedup"
    )
    ingestion_key: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="deterministic source replay key"
    )
    raw_price_text: Mapped[str | None] = mapped_column(String(200))


class ExternalCollectionRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single run of the price collection job. Tracks progress for resumability."""

    __tablename__ = "price_intelligence_external_collection_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('pending','running','completed','failed','cancelled')",
            name="valid_collection_run_status",
        ),
        Index("ix_collection_runs_source_id_started", "source_id", "started_at"),
    )

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("price_intelligence_external_price_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")

    # Counts (integer counters, nullable while in progress)
    pages_requested: Mapped[int | None] = mapped_column(Integer)
    pages_succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prices_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class ExchangeRateSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A point-in-time FX observation. Stored separately from prices.
    No observation is ever replaced by a converted value.
    """

    __tablename__ = "price_intelligence_exchange_rate_snapshots"
    __table_args__ = (
        CheckConstraint("rate > 0", name="valid_exchange_rate"),
        Index(
            "ix_exchange_rates_base_quote_observed",
            "base_currency",
            "quote_currency",
            "observed_at",
        ),
    )

    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # rate stored as high-precision decimal via string to avoid float pitfalls
    rate: Mapped[Decimal] = mapped_column(
        Numeric(24, 12), nullable=False, comment="Decimal rate from base to quote"
    )
    provider: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Source of the rate (e.g. ECB, CB_AM)"
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
