"""Price intelligence service layer.

Business logic for external product ingestion, matching, and price observations.
Keeps all operations idempotent and auditable. Never mutates canonical catalog.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.core.config import get_settings
from app.integrations.price_intelligence.matcher import (
    CandidateMatch,
    MatchMethod,
    MatchReason,
    MatchResult,
    run_matching_pipeline,
)
from app.modules.catalog.models import Offer, Product
from app.modules.price_intelligence.models import (
    ExternalCollectionRun,
    ExternalPriceObservation,
    ExternalPriceSource,
    ExternalProduct,
    ExternalProductMatch,
    ExternalSeller,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestProductResult:
    """Result of ingesting a single external product."""

    external_product_id: UUID
    created: bool
    updated: bool
    match_result: MatchResult | None = None
    observation_id: UUID | None = None


@dataclass(slots=True)
class IngestRunResult:
    """Aggregate result of a full collection run."""

    run_id: UUID
    products_seen: int = 0
    products_created: int = 0
    products_updated: int = 0
    prices_inserted: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class PriceIntelligenceService:
    """Stateless service for price intelligence operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Source management
    # ------------------------------------------------------------------

    async def get_or_create_source(
        self,
        code: str,
        *,
        name: str,
        base_url: str,
        country_code: str,
        default_currency: str,
        source_type: str = "marketplace",
    ) -> ExternalPriceSource:
        """Idempotently fetch or create an external price source."""
        result = await self._session.execute(
            select(ExternalPriceSource).where(ExternalPriceSource.code == code)
        )
        source = result.scalar_one_or_none()
        if source is not None:
            return source

        source = ExternalPriceSource(
            id=uuid4(),
            code=code,
            name=name,
            base_url=base_url,
            country_code=country_code,
            default_currency=default_currency,
            source_type=source_type,
            collection_enabled=False,  # Feature-flagged, gated by default.
        )
        self._session.add(source)
        await self._session.flush()
        logger.info("Created external price source code=%s", code)
        return source

    async def get_source(self, code: str) -> ExternalPriceSource | None:
        result = await self._session.execute(
            select(ExternalPriceSource).where(ExternalPriceSource.code == code)
        )
        return result.scalar_one_or_none()

    async def update_source_policy(
        self,
        source_id: UUID,
        *,
        collection_enabled: bool | None = None,
        robots_status: str | None = None,
        robots_checked_at: datetime | None = None,
        terms_status: str | None = None,
        terms_checked_at: datetime | None = None,
        terms_evidence_url: str | None = None,
    ) -> ExternalPriceSource | None:
        """Update source policy fields (robots/terms/enabled)."""
        source = await self._session.get(ExternalPriceSource, source_id)
        if source is None:
            return None
        if collection_enabled is not None:
            source.collection_enabled = collection_enabled
        if robots_status is not None:
            source.robots_status = robots_status
        if robots_checked_at is not None:
            source.robots_checked_at = robots_checked_at
        if terms_status is not None:
            source.terms_status = terms_status
        if terms_checked_at is not None:
            source.terms_checked_at = terms_checked_at
        if terms_evidence_url is not None:
            source.terms_evidence_url = terms_evidence_url
        await self._session.flush()
        return source

    # ------------------------------------------------------------------
    # Seller management
    # ------------------------------------------------------------------

    async def get_or_create_seller(
        self,
        source_id: UUID,
        *,
        seller_name: str,
        external_seller_id: str | None = None,
        seller_url: str | None = None,
    ) -> ExternalSeller:
        """Idempotently ensure a seller exists for a source."""
        now = utc_now()
        # Lookup by external_seller_id first, then by seller_name
        stmt = select(ExternalSeller).where(
            and_(
                ExternalSeller.source_id == source_id,
                or_(
                    ExternalSeller.external_seller_id == external_seller_id
                    if external_seller_id
                    else False,
                    ExternalSeller.seller_name == seller_name,
                ),
            )
        )
        result = await self._session.execute(stmt)
        seller = result.scalar_one_or_none()
        if seller is not None:
            seller.last_seen_at = now
            await self._session.flush()
            return seller

        seller = ExternalSeller(
            id=uuid4(),
            source_id=source_id,
            external_seller_id=external_seller_id,
            seller_name=seller_name,
            seller_url=seller_url,
            first_seen_at=now,
            last_seen_at=now,
        )
        self._session.add(seller)
        await self._session.flush()
        logger.info("Created external seller seller_name=%s source_id=%s", seller_name, source_id)
        return seller

    # ------------------------------------------------------------------
    # External product management (upsert)
    # ------------------------------------------------------------------

    async def upsert_external_product(
        self,
        source_id: UUID,
        external_product_id: str,
        *,
        source_url: str,
        source_title: str,
        brand_name: str,
        species: str | None = None,
        food_type: str | None = None,
        life_stage: str | None = None,
        product_line: str | None = None,
        formula_name: str | None = None,
        veterinary_diet: bool | None = None,
        declared_pack_count: int | None = None,
        declared_unit_weight_g: int | None = None,
        declared_total_weight_g: int | None = None,
        raw_pack_text: str | None = None,
        availability: str = "unknown",
        seller_id: UUID | None = None,
        raw_payload_json: dict[str, Any] | None = None,
    ) -> tuple[ExternalProduct, bool]:
        """
        Upsert an external product. Returns (product, created).
        Idempotent by (source_id, external_product_id).
        """
        now = utc_now()
        result = await self._session.execute(
            select(ExternalProduct).where(
                and_(
                    ExternalProduct.source_id == source_id,
                    ExternalProduct.external_product_id == external_product_id,
                )
            )
        )
        product = result.scalar_one_or_none()

        if product is None:
            product = ExternalProduct(
                id=uuid4(),
                source_id=source_id,
                external_product_id=external_product_id,
                first_seen_at=now,
            )
            self._session.add(product)
            created = True
        else:
            created = False

        # Always update volatile fields
        product.source_url = source_url
        product.source_title = source_title
        product.brand_name = brand_name
        product.species = species
        product.food_type = food_type
        product.life_stage = life_stage
        product.product_line = product_line
        product.formula_name = formula_name
        product.veterinary_diet = veterinary_diet
        product.declared_pack_count = declared_pack_count
        product.declared_unit_weight_g = declared_unit_weight_g
        product.declared_total_weight_g = declared_total_weight_g
        product.raw_pack_text = raw_pack_text
        product.availability = availability
        product.seller_id = seller_id
        product.last_seen_at = now
        if raw_payload_json is not None:
            product.raw_payload_json = raw_payload_json

        await self._session.flush()
        return product, created

    # ------------------------------------------------------------------
    # Match management
    # ------------------------------------------------------------------

    async def run_match_for_product(
        self,
        external_product: ExternalProduct,
    ) -> MatchResult:
        """
        Run the multi-tier matching pipeline against canonical catalog.
        Creates/updates an ExternalProductMatch row with full reasoning.
        """
        # Build candidate from external product
        candidate = CandidateMatch(
            external_product_id=external_product.id,
            external_source_id=external_product.source_id,
            brand_name=external_product.brand_name,
            species=external_product.species,
            food_type=external_product.food_type,
            life_stage=external_product.life_stage,
            product_line=external_product.product_line,
            formula_name=external_product.formula_name,
            veterinary_diet=external_product.veterinary_diet,
            declared_pack_count=external_product.declared_pack_count,
            declared_unit_weight_g=external_product.declared_unit_weight_g,
            declared_total_weight_g=external_product.declared_total_weight_g,
            source_title=external_product.source_title,
        )

        # Fetch canonical catalog items to match against
        canon_query = select(Product).where(Product.status == "active")
        canon_result = await self._session.execute(canon_query)
        canon_products = list(canon_result.scalars().all())

        # Run pipeline (deterministic, no side effects)
        match_result = run_matching_pipeline(candidate, canon_products)

        # Upsert match row
        match_query = select(ExternalProductMatch).where(
            ExternalProductMatch.external_product_id == external_product.id
        )
        existing = (await self._session.execute(match_query)).scalar_one_or_none()

        if existing is not None:
            existing.canonical_product_id = match_result.canonical_product_id
            existing.canonical_variant_id = match_result.canonical_variant_id
            existing.canonical_ean = match_result.canonical_ean
            existing.match_method = match_result.method.value
            existing.match_confidence = match_result.confidence
            existing.match_status = match_result.status
            existing.match_reasons_json = {
                "reasons": [r.value for r in match_result.reasons],
                "warnings": list(match_result.warnings),
            }
        else:
            new_match = ExternalProductMatch(
                id=uuid4(),
                external_product_id=external_product.id,
                canonical_product_id=match_result.canonical_product_id,
                canonical_variant_id=match_result.canonical_variant_id,
                canonical_ean=match_result.canonical_ean,
                match_method=match_result.method.value,
                match_confidence=match_result.confidence,
                match_status=match_result.status,
                match_reasons_json={
                    "reasons": [r.value for r in match_result.reasons],
                    "warnings": list(match_result.warnings),
                },
            )
            self._session.add(new_match)

        await self._session.flush()
        return match_result

    async def approve_match(
        self,
        match_id: UUID,
        reviewed_by: UUID,
    ) -> ExternalProductMatch | None:
        """Operator approves a match (idempotent)."""
        match = await self._session.get(ExternalProductMatch, match_id)
        if match is None:
            return None
        match.match_status = "approved"
        match.reviewed_by = reviewed_by
        match.reviewed_at = utc_now()
        await self._session.flush()
        logger.info("Approved match %s by operator %s", match_id, reviewed_by)
        return match

    async def reject_match(
        self,
        match_id: UUID,
        reviewed_by: UUID,
    ) -> ExternalProductMatch | None:
        """Operator rejects a match (idempotent)."""
        match = await self._session.get(ExternalProductMatch, match_id)
        if match is None:
            return None
        match.match_status = "rejected"
        match.reviewed_by = reviewed_by
        match.reviewed_at = utc_now()
        await self._session.flush()
        logger.info("Rejected match %s by operator %s", match_id, reviewed_by)
        return match

    async def remap_match(
        self,
        match_id: UUID,
        reviewed_by: UUID,
        *,
        canonical_product_id: UUID,
        canonical_variant_id: UUID | None = None,
    ) -> ExternalProductMatch | None:
        """Operator manually remaps a match to a different canonical product."""
        match = await self._session.get(ExternalProductMatch, match_id)
        if match is None:
            return None
        match.canonical_product_id = canonical_product_id
        match.canonical_variant_id = canonical_variant_id
        match.match_method = "manual"
        match.match_status = "approved"
        match.match_confidence = 1.0
        match.reviewed_by = reviewed_by
        match.reviewed_at = utc_now()
        await self._session.flush()
        logger.info("Remapped match %s to product %s by operator %s", match_id, canonical_product_id, reviewed_by)
        return match

    # ------------------------------------------------------------------
    # Price observations (immutable append-only)
    # ------------------------------------------------------------------

    async def insert_observation(
        self,
        external_product_id: UUID,
        *,
        seller_id: UUID | None,
        currency: str,
        price_minor: int,
        compare_at_price_minor: int | None,
        pack_count: int | None,
        unit_weight_g: int | None,
        total_weight_g: int | None,
        availability: str,
        observed_at: datetime,
        collection_run_id: UUID | None,
        raw_price_text: str | None,
    ) -> ExternalPriceObservation | None:
        """
        Insert a single price observation. Deduplicates by content_hash.
        Never overwrites historical observations; returns None if duplicate.
        """
        # Build content hash from the core pricing payload
        content_payload = {
            "price_minor": price_minor,
            "compare_at_price_minor": compare_at_price_minor,
            "pack_count": pack_count,
            "unit_weight_g": unit_weight_g,
            "total_weight_g": total_weight_g,
            "availability": availability,
            "currency": currency,
        }
        content_hash = hashlib.sha256(json.dumps(content_payload, sort_keys=True).encode()).hexdigest()

        # Check for exact dedup (same product + seller + observed_at)
        existing = await self._session.execute(
            select(ExternalPriceObservation).where(
                and_(
                    ExternalPriceObservation.external_product_id == external_product_id,
                    ExternalPriceObservation.seller_id == seller_id,
                    ExternalPriceObservation.observed_at == observed_at,
                )
            )
        )
        if existing.scalar_one_or_none() is not None:
            return None  # Idempotent: already recorded.

        # Derive unit_price_per_kg_minor only from reliable weights
        unit_price_per_kg_minor: int | None = None
        if total_weight_g and total_weight_g > 0 and price_minor and price_minor > 0:
            unit_price_per_kg_minor = (price_minor * 1000) // total_weight_g

        obs = ExternalPriceObservation(
            id=uuid4(),
            external_product_id=external_product_id,
            seller_id=seller_id,
            currency=currency,
            price_minor=price_minor,
            compare_at_price_minor=compare_at_price_minor,
            pack_count=pack_count,
            unit_weight_g=unit_weight_g,
            total_weight_g=total_weight_g,
            unit_price_per_kg_minor=unit_price_per_kg_minor,
            availability=availability,
            observed_at=observed_at,
            collection_run_id=collection_run_id,
            content_hash=content_hash,
            raw_price_text=raw_price_text,
        )
        self._session.add(obs)
        await self._session.flush()
        return obs

    # ------------------------------------------------------------------
    # Collection runs
    # ------------------------------------------------------------------

    async def create_collection_run(
        self,
        source_id: UUID,
        *,
        pages_requested: int | None = None,
    ) -> ExternalCollectionRun:
        """Start a new collection run."""
        run = ExternalCollectionRun(
            id=uuid4(),
            source_id=source_id,
            started_at=utc_now(),
            status="running",
            pages_requested=pages_requested,
            pages_succeeded=0,
            products_seen=0,
            products_created=0,
            products_updated=0,
            prices_inserted=0,
            warnings_count=0,
            errors_count=0,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def complete_collection_run(
        self,
        run_id: UUID,
        *,
        status: str = "completed",
        products_seen: int = 0,
        products_created: int = 0,
        products_updated: int = 0,
        prices_inserted: int = 0,
        pages_succeeded: int = 0,
        warnings_count: int = 0,
        errors_count: int = 0,
        error_summary_json: dict[str, Any] | None = None,
    ) -> ExternalCollectionRun | None:
        """Finalize a collection run."""
        run = await self._session.get(ExternalCollectionRun, run_id)
        if run is None:
            return None
        run.status = status
        run.completed_at = utc_now()
        run.products_seen = products_seen
        run.products_created = products_created
        run.products_updated = products_updated
        run.prices_inserted = prices_inserted
        run.pages_succeeded = pages_succeeded
        run.warnings_count = warnings_count
        run.errors_count = errors_count
        run.error_summary_json = error_summary_json
        await self._session.flush()
        return run

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    async def list_pending_matches(self, limit: int = 50) -> list[ExternalProductMatch]:
        stmt = (
            select(ExternalProductMatch)
            .where(
                ExternalProductMatch.match_status.in_(("suggested", "needs_review"))
            )
            .order_by(ExternalProductMatch.match_confidence.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_product_price_history(
        self,
        external_product_id: UUID,
        limit: int = 100,
    ) -> list[ExternalPriceObservation]:
        stmt = (
            select(ExternalPriceObservation)
            .where(ExternalPriceObservation.external_product_id == external_product_id)
            .order_by(ExternalPriceObservation.observed_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_canonical_product_market_prices(
        self,
        canonical_product_id: UUID,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Latest approved prices for all external products mapped to a canonical product."""
        stmt = (
            select(
                ExternalProductMatch,
                ExternalProduct,
                func.max(ExternalPriceObservation.observed_at).label("latest_observed_at"),
            )
            .join(
                ExternalProduct,
                ExternalProduct.id == ExternalProductMatch.external_product_id,
            )
            .outerjoin(
                ExternalPriceObservation,
                ExternalPriceObservation.external_product_id == ExternalProduct.id,
            )
            .where(
                and_(
                    ExternalProductMatch.canonical_product_id == canonical_product_id,
                    ExternalProductMatch.match_status == "approved",
                )
            )
            .group_by(ExternalProductMatch.id, ExternalProduct.id)
            .order_by(func.max(ExternalPriceObservation.observed_at).desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.all()
        out: list[dict[str, Any]] = []
        for match_row, product_row, latest_ts in rows:
            out.append(
                {
                    "match_id": match_row.id,
                    "external_product_id": product_row.id,
                    "external_product_title": product_row.source_title,
                    "source_url": product_row.source_url,
                    "latest_observed_at": latest_ts,
                    "match_method": match_row.match_method,
                    "match_confidence": match_row.match_confidence,
                }
            )
        return out

    async def list_collection_runs(
        self, source_id: UUID | None = None, limit: int = 20
    ) -> list[ExternalCollectionRun]:
        stmt = select(ExternalCollectionRun).order_by(
            ExternalCollectionRun.started_at.desc()
        )
        if source_id is not None:
            stmt = stmt.where(ExternalCollectionRun.source_id == source_id)
        stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
