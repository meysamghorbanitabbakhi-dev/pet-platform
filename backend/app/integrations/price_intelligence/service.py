"""Canonical price-intelligence service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.integrations.price_intelligence.matcher import (
    CandidateMatch,
    MatchMethod,
    MatchResult,
    run_matching_pipeline,
)
from app.integrations.price_intelligence.petmall_am_parser import ParsedExternalProduct
from app.modules.catalog.models import Offer, Product
from app.modules.price_intelligence.models import (
    ExchangeRateSnapshot,
    ExternalCollectionRun,
    ExternalPriceObservation,
    ExternalPriceSource,
    ExternalProduct,
    ExternalProductMatch,
    ExternalProductMatchReview,
    ExternalSeller,
)


@dataclass(frozen=True, slots=True)
class FxConversionResult:
    amount_minor: int
    source_currency: str
    target_currency: str
    rate: Decimal
    provider: str
    observed_at: datetime
    policy_blocked: bool = False


class ObservationIdentityConflict(RuntimeError):
    """The observation natural identity already belongs to different content."""


@dataclass(frozen=True, slots=True)
class ObservationInsertResult:
    observation: ExternalPriceObservation
    created: bool


class PriceIntelligenceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        result = await self._session.execute(
            select(ExternalPriceSource).where(ExternalPriceSource.code == code)
        )
        source = result.scalar_one_or_none()
        if source:
            return source
        source = ExternalPriceSource(
            id=uuid4(),
            code=code,
            name=name,
            base_url=base_url,
            country_code=country_code,
            default_currency=default_currency,
            source_type=source_type,
            collection_enabled=False,
        )
        self._session.add(source)
        await self._session.flush()
        return source

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
        source = await self._session.get(ExternalPriceSource, source_id)
        if source is None:
            return None
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
        if collection_enabled is not None:
            if collection_enabled and not self.source_policy_allows_collection(source):
                raise ValueError("source_policy_not_approved")
            source.collection_enabled = collection_enabled
        await self._session.flush()
        return source

    def source_policy_allows_collection(self, source: ExternalPriceSource) -> bool:
        return source.robots_status == "allowed" and source.terms_status == "accepted"

    async def get_or_create_seller(
        self,
        source_id: UUID,
        *,
        seller_name: str,
        external_seller_id: str | None = None,
        seller_url: str | None = None,
    ) -> ExternalSeller:
        conditions = [ExternalSeller.source_id == source_id]
        if external_seller_id:
            conditions.append(ExternalSeller.external_seller_id == external_seller_id)
        else:
            conditions.append(ExternalSeller.seller_name == seller_name)
        result = await self._session.execute(select(ExternalSeller).where(and_(*conditions)))
        seller = result.scalar_one_or_none()
        now = utc_now()
        if seller:
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
        return seller

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
        raw_payload_json: dict[str, object] | None = None,
    ) -> tuple[ExternalProduct, bool]:
        result = await self._session.execute(
            select(ExternalProduct).where(
                ExternalProduct.source_id == source_id,
                ExternalProduct.external_product_id == external_product_id,
            )
        )
        product = result.scalar_one_or_none()
        now = utc_now()
        created = product is None
        if product is None:
            product = ExternalProduct(
                id=uuid4(),
                source_id=source_id,
                external_product_id=external_product_id,
                first_seen_at=now,
            )
            self._session.add(product)
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
        product.raw_payload_json = raw_payload_json
        await self._session.flush()
        return product, created

    async def ingest_parsed_product(
        self,
        source: ExternalPriceSource,
        parsed: ParsedExternalProduct,
        *,
        collection_run_id: UUID | None,
    ) -> tuple[ExternalProduct, ObservationInsertResult]:
        seller = await self.get_or_create_seller(
            source.id,
            seller_name=parsed.seller_name or source.name,
        )
        product, _created = await self.upsert_external_product(
            source.id,
            parsed.external_product_id,
            source_url=parsed.url,
            source_title=parsed.title,
            brand_name=parsed.brand,
            declared_pack_count=parsed.packaging.pack_count,
            declared_unit_weight_g=parsed.packaging.unit_weight_g,
            declared_total_weight_g=parsed.packaging.total_weight_g,
            raw_pack_text=parsed.packaging.raw_text,
            availability=parsed.availability,
            seller_id=seller.id,
            raw_payload_json=parsed.raw_data,
        )
        observation = await self.insert_observation(
            product.id,
            seller_id=seller.id,
            currency=parsed.price.currency,
            currency_exponent=parsed.price.currency_exponent,
            price_minor=parsed.price.amount_minor,
            compare_at_price_minor=None,
            pack_count=parsed.packaging.pack_count,
            unit_weight_g=parsed.packaging.unit_weight_g,
            total_weight_g=parsed.packaging.total_weight_g,
            availability=parsed.availability,
            observed_at=parsed.collected_at,
            collection_run_id=collection_run_id,
            raw_price_text=parsed.price.raw_text,
        )
        await self.run_match_for_product(product, external_sku=parsed.sku)
        return product, observation

    async def run_match_for_product(
        self,
        external_product: ExternalProduct,
        *,
        external_sku: str | None = None,
    ) -> MatchResult:
        candidate = CandidateMatch(
            external_product_id=external_product.id,
            external_source_id=external_product.source_id,
            brand_name=external_product.brand_name,
            source_title=external_product.source_title,
            external_sku=external_sku,
            species=external_product.species,
            food_type=external_product.food_type,
            life_stage=external_product.life_stage,
            product_line=external_product.product_line,
            formula_name=external_product.formula_name,
            veterinary_diet=external_product.veterinary_diet,
            declared_pack_count=external_product.declared_pack_count,
            declared_unit_weight_g=external_product.declared_unit_weight_g,
            declared_total_weight_g=external_product.declared_total_weight_g,
        )
        products = list(
            (
                await self._session.execute(select(Product).where(Product.status == "active"))
            ).scalars()
        )
        result = run_matching_pipeline(candidate, products)
        match = (
            await self._session.execute(
                select(ExternalProductMatch).where(
                    ExternalProductMatch.external_product_id == external_product.id
                )
            )
        ).scalar_one_or_none()
        if match is None:
            match = ExternalProductMatch(id=uuid4(), external_product_id=external_product.id)
            self._session.add(match)
        match.canonical_product_id = result.canonical_product_id
        match.canonical_variant_id = result.canonical_variant_id
        match.canonical_ean = result.canonical_ean
        match.match_method = result.method.value
        match.match_status = result.status
        match.match_confidence = result.confidence
        match.match_reasons_json = {
            "reasons": [reason.value for reason in result.reasons],
            "warnings": result.warnings,
        }
        await self._session.flush()
        return result

    async def insert_observation(
        self,
        external_product_id: UUID,
        *,
        seller_id: UUID | None,
        currency: str,
        currency_exponent: int,
        price_minor: int,
        compare_at_price_minor: int | None = None,
        pack_count: int | None = None,
        unit_weight_g: int | None = None,
        total_weight_g: int | None = None,
        availability: str,
        observed_at: datetime,
        collection_run_id: UUID | None = None,
        raw_price_text: str | None = None,
    ) -> ObservationInsertResult:
        if price_minor <= 0:
            raise ValueError("price_minor_must_be_positive")
        payload = {
            "currency": currency,
            "currency_exponent": currency_exponent,
            "price_minor": price_minor,
            "compare_at_price_minor": compare_at_price_minor,
            "availability": availability,
            "pack_count": pack_count,
            "unit_weight_g": unit_weight_g,
            "total_weight_g": total_weight_g,
            "raw_price_text": raw_price_text,
        }
        content_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        seller_part = str(seller_id) if seller_id else "no-seller"
        ingestion_key = hashlib.sha256(
            f"{external_product_id}:{seller_part}:{observed_at.isoformat()}".encode()
        ).hexdigest()
        natural_key = (
            ExternalPriceObservation.external_product_id == external_product_id,
            ExternalPriceObservation.seller_id.is_not_distinct_from(seller_id),
            ExternalPriceObservation.observed_at == observed_at,
        )
        legacy = (
            await self._session.execute(select(ExternalPriceObservation).where(*natural_key))
        ).scalar_one_or_none()
        if legacy is not None:
            if legacy.content_hash != content_hash:
                raise ObservationIdentityConflict(
                    "observation natural key already exists with different content"
                )
            return ObservationInsertResult(observation=legacy, created=False)
        unit_price = (price_minor * 1000) // total_weight_g if total_weight_g else None
        observation_id = uuid4()
        values = dict(
            id=observation_id,
            external_product_id=external_product_id,
            seller_id=seller_id,
            currency=currency,
            currency_exponent=currency_exponent,
            price_minor=price_minor,
            compare_at_price_minor=compare_at_price_minor,
            pack_count=pack_count,
            unit_weight_g=unit_weight_g,
            total_weight_g=total_weight_g,
            unit_price_per_kg_minor=unit_price,
            availability=availability,
            observed_at=observed_at,
            collection_run_id=collection_run_id,
            content_hash=content_hash,
            ingestion_key=ingestion_key,
            raw_price_text=raw_price_text,
        )
        inserted_id = (
            await self._session.execute(
                insert(ExternalPriceObservation)
                .values(**values)
                .on_conflict_do_nothing()
                .returning(ExternalPriceObservation.id)
            )
        ).scalar_one_or_none()
        if inserted_id is not None:
            observation = await self._session.get(ExternalPriceObservation, inserted_id)
            assert observation is not None
            return ObservationInsertResult(observation=observation, created=True)

        existing = (
            await self._session.execute(
                select(ExternalPriceObservation).where(
                    ExternalPriceObservation.ingestion_key == ingestion_key
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = (
                await self._session.execute(select(ExternalPriceObservation).where(*natural_key))
            ).scalar_one_or_none()
        if existing is None:
            raise RuntimeError("observation_conflict_without_existing_row")
        if existing.content_hash != content_hash:
            raise ObservationIdentityConflict(
                "observation natural key already exists with different content"
            )
        return ObservationInsertResult(observation=existing, created=False)

    async def approve_match(
        self,
        match_id: UUID,
        reviewed_by: UUID,
        *,
        reason: str,
    ) -> ExternalProductMatch | None:
        return await self._review_match(match_id, reviewed_by, "approved", reason=reason)

    async def reject_match(
        self,
        match_id: UUID,
        reviewed_by: UUID,
        *,
        reason: str,
    ) -> ExternalProductMatch | None:
        return await self._review_match(match_id, reviewed_by, "rejected", reason=reason)

    async def remap_match(
        self,
        match_id: UUID,
        reviewed_by: UUID,
        *,
        canonical_product_id: UUID,
        canonical_variant_id: UUID | None,
        reason: str,
    ) -> ExternalProductMatch | None:
        if await self._session.get(Product, canonical_product_id) is None:
            raise ValueError("canonical_product_not_found")
        if (
            canonical_variant_id is not None
            and await self._session.get(Offer, canonical_variant_id) is None
        ):
            raise ValueError("canonical_offer_not_found")
        return await self._review_match(
            match_id,
            reviewed_by,
            "remapped",
            reason=reason,
            canonical_product_id=canonical_product_id,
            canonical_variant_id=canonical_variant_id,
        )

    async def _review_match(
        self,
        match_id: UUID,
        reviewed_by: UUID,
        decision: str,
        *,
        reason: str,
        canonical_product_id: UUID | None = None,
        canonical_variant_id: UUID | None = None,
    ) -> ExternalProductMatch | None:
        match = await self._session.get(ExternalProductMatch, match_id)
        if match is None:
            return None
        previous_status = match.match_status
        previous_product = str(match.canonical_product_id) if match.canonical_product_id else None
        if decision == "remapped":
            match.canonical_product_id = canonical_product_id
            match.canonical_variant_id = canonical_variant_id
            match.match_method = MatchMethod.MANUAL.value
            match.match_confidence = 1.0
            match.match_status = "approved"
        else:
            match.match_status = decision
        match.reviewed_by = reviewed_by
        match.reviewed_at = utc_now()
        self._session.add(
            ExternalProductMatchReview(
                id=uuid4(),
                match_id=match.id,
                operator_id=reviewed_by,
                decision=decision,
                previous_status=previous_status,
                previous_canonical_product_id=previous_product,
                new_canonical_product_id=str(match.canonical_product_id)
                if match.canonical_product_id
                else None,
                reason=reason,
                decided_at=utc_now(),
            )
        )
        await self._session.flush()
        return match

    async def create_collection_run(
        self, source_id: UUID, *, pages_requested: int | None = None
    ) -> ExternalCollectionRun:
        run = ExternalCollectionRun(
            id=uuid4(),
            source_id=source_id,
            started_at=utc_now(),
            status="running",
            pages_requested=pages_requested,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def complete_collection_run(
        self,
        run_id: UUID,
        *,
        status: str,
        products_seen: int = 0,
        products_created: int = 0,
        products_updated: int = 0,
        prices_inserted: int = 0,
        pages_succeeded: int = 0,
        warnings_count: int = 0,
        errors_count: int = 0,
        error_summary_json: dict[str, object] | None = None,
    ) -> ExternalCollectionRun | None:
        run = await self._session.get(ExternalCollectionRun, run_id)
        if run is None:
            return None
        run.status = status
        run.completed_at = utc_now()
        run.products_seen = max(0, products_seen)
        run.products_created = max(0, products_created)
        run.products_updated = max(0, products_updated)
        run.prices_inserted = max(0, prices_inserted)
        run.pages_succeeded = max(0, pages_succeeded)
        run.warnings_count = max(0, warnings_count)
        run.errors_count = max(0, errors_count)
        run.error_summary_json = error_summary_json
        await self._session.flush()
        return run

    async def list_pending_matches(self, limit: int = 50) -> list[ExternalProductMatch]:
        result = await self._session.execute(
            select(ExternalProductMatch)
            .where(ExternalProductMatch.match_status.in_(("suggested", "needs_review")))
            .order_by(ExternalProductMatch.match_confidence.desc())
            .limit(min(limit, 100))
        )
        return list(result.scalars())

    async def get_product_price_history(
        self, external_product_id: UUID, limit: int = 100
    ) -> list[ExternalPriceObservation]:
        result = await self._session.execute(
            select(ExternalPriceObservation)
            .where(ExternalPriceObservation.external_product_id == external_product_id)
            .order_by(ExternalPriceObservation.observed_at.desc())
            .limit(min(limit, 200))
        )
        return list(result.scalars())

    async def get_canonical_product_market_prices(
        self, canonical_product_id: UUID, limit: int = 20
    ) -> list[dict[str, object]]:
        latest = (
            select(
                ExternalPriceObservation.external_product_id.label("external_product_id"),
                func.max(ExternalPriceObservation.observed_at).label("latest_observed_at"),
            )
            .group_by(ExternalPriceObservation.external_product_id)
            .subquery()
        )
        result = await self._session.execute(
            select(ExternalProductMatch, ExternalProduct, ExternalPriceObservation)
            .join(ExternalProduct, ExternalProduct.id == ExternalProductMatch.external_product_id)
            .join(latest, latest.c.external_product_id == ExternalProduct.id)
            .join(
                ExternalPriceObservation,
                and_(
                    ExternalPriceObservation.external_product_id == ExternalProduct.id,
                    ExternalPriceObservation.observed_at == latest.c.latest_observed_at,
                ),
            )
            .where(
                ExternalProductMatch.canonical_product_id == canonical_product_id,
                ExternalProductMatch.match_status == "approved",
            )
            .order_by(ExternalPriceObservation.observed_at.desc())
            .limit(min(limit, 100))
        )
        return [
            {
                "match_id": match.id,
                "external_product_id": product.id,
                "external_product_title": product.source_title,
                "source_url": product.source_url,
                "price_minor": observation.price_minor,
                "currency": observation.currency,
                "availability": observation.availability,
                "latest_observed_at": observation.observed_at,
                "match_method": match.match_method,
                "match_confidence": match.match_confidence,
            }
            for match, product, observation in result.all()
        ]

    async def list_collection_runs(
        self, source_id: UUID | None = None, limit: int = 20
    ) -> list[ExternalCollectionRun]:
        stmt = select(ExternalCollectionRun).order_by(ExternalCollectionRun.started_at.desc())
        if source_id:
            stmt = stmt.where(ExternalCollectionRun.source_id == source_id)
        result = await self._session.execute(stmt.limit(min(limit, 100)))
        return list(result.scalars())

    async def convert_with_fx(
        self,
        *,
        amount_minor: int,
        source_currency: str,
        target_currency: str,
    ) -> FxConversionResult | None:
        snapshot = (
            await self._session.execute(
                select(ExchangeRateSnapshot)
                .where(
                    ExchangeRateSnapshot.base_currency == source_currency,
                    ExchangeRateSnapshot.quote_currency == target_currency,
                )
                .order_by(ExchangeRateSnapshot.observed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if snapshot is None:
            return None
        amount = (Decimal(amount_minor) * snapshot.rate).quantize(Decimal("1"), ROUND_HALF_UP)
        return FxConversionResult(
            amount_minor=int(amount),
            source_currency=source_currency,
            target_currency=target_currency,
            rate=snapshot.rate,
            provider=snapshot.provider,
            observed_at=snapshot.observed_at,
            policy_blocked=True,
        )
