from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.pet_health.models import BenchmarkDefinition
from app.modules.pet_knowledge.models import (
    KnowledgeBreed,
    KnowledgeClaim,
    KnowledgeClaimSource,
    KnowledgeRelease,
    KnowledgeSource,
    KnowledgeVariety,
)
from app.modules.pet_knowledge.validation import ValidationResult


async def import_validated_bundle(
    session: AsyncSession,
    *,
    bundle: dict[str, Any],
    validation: ValidationResult,
    storage_key: str,
    operator_id: UUID,
) -> KnowledgeRelease:
    if not validation.valid:
        raise ValueError("knowledge_bundle_invalid")
    release = KnowledgeRelease(
        schema_version=bundle["schema_version"],
        dataset_version=bundle["dataset_version"],
        language=bundle["language"],
        status="imported",
        checksum_sha256=validation.checksum_sha256,
        storage_key=storage_key,
        imported_by_operator_id=operator_id,
        imported_at=utc_now(),
        breed_count=validation.counts["breeds"],
        variety_count=validation.counts["varieties"],
        source_count=validation.counts["sources"],
        claim_count=validation.counts["claims"],
    )
    session.add(release)
    await session.flush()

    for record in bundle["breeds"]:
        session.add(
            KnowledgeBreed(
                release_id=release.id,
                external_id=record["id"],
                species=record["species"],
                name_fa=record["name_fa"],
                name_en=record["name_en"],
                record=record,
            )
        )
    for record in bundle["varieties"]:
        session.add(
            KnowledgeVariety(
                release_id=release.id,
                external_id=record["id"],
                breed_external_id=record["breed_id"],
                name_fa=record["name_fa"],
                name_en=record["name_en"],
                record=record,
            )
        )
    sources: dict[str, KnowledgeSource] = {}
    for record in bundle["sources"]:
        source = KnowledgeSource(
            release_id=release.id,
            external_id=record["id"],
            source_type=record["type"],
            title=record["title"],
            record=record,
        )
        session.add(source)
        sources[record["id"]] = source
    await session.flush()
    for record in bundle["claims"]:
        stored_record = {**record, "app_eligible": False}
        claim = KnowledgeClaim(
            release_id=release.id,
            external_id=record["id"],
            breed_external_id=record["breed_id"],
            variety_external_id=record.get("variety_id"),
            claim_type=record["claim_type"],
            text_fa=record["text_fa"],
            review_status=record["review_status"],
            app_eligible=False,
            record=stored_record,
        )
        session.add(claim)
        await session.flush()
        for source_id in record["source_ids"]:
            session.add(KnowledgeClaimSource(claim_id=claim.id, source_id=sources[source_id].id))
    return release


async def materialize_release_benchmarks(
    session: AsyncSession, *, release: KnowledgeRelease, operator_id: UUID
) -> dict[str, int]:
    """Materialize structured quantitative references without parsing display text."""
    claims = list(
        (
            await session.scalars(
                select(KnowledgeClaim).where(
                    KnowledgeClaim.release_id == release.id,
                    KnowledgeClaim.claim_type.in_(("adult_weight_reference", "height_reference")),
                    KnowledgeClaim.review_status == "veterinary_approved",
                    KnowledgeClaim.app_eligible.is_(True),
                )
            )
        ).all()
    )
    created = skipped = 0
    for claim in claims:
        existing = await session.scalar(
            select(BenchmarkDefinition.id).where(BenchmarkDefinition.claim_id == claim.id)
        )
        if existing is not None:
            skipped += 1
            continue
        target: KnowledgeBreed | KnowledgeVariety | None
        if claim.variety_external_id is not None:
            target = await session.scalar(
                select(KnowledgeVariety).where(
                    KnowledgeVariety.release_id == release.id,
                    KnowledgeVariety.external_id == claim.variety_external_id,
                )
            )
        else:
            target = await session.scalar(
                select(KnowledgeBreed).where(
                    KnowledgeBreed.release_id == release.id,
                    KnowledgeBreed.external_id == claim.breed_external_id,
                )
            )
        field = (
            "adult_weight_reference"
            if claim.claim_type == "adult_weight_reference"
            else "height_reference"
        )
        reference = target.record.get(field) if target is not None else None
        if not isinstance(reference, dict) or reference.get("status") != "available":
            skipped += 1
            continue
        minimum, maximum, unit = (
            reference.get("min"),
            reference.get("max"),
            reference.get("unit"),
        )
        expected_unit = "kg" if claim.claim_type == "adult_weight_reference" else "cm"
        if not isinstance(minimum, (int, float)) or not isinstance(maximum, (int, float)):
            skipped += 1
            continue
        if unit != expected_unit or minimum < 0 or maximum < minimum:
            skipped += 1
            continue
        record = claim.record
        purpose = record.get("reference_purpose")
        if purpose != "registry_conformation_reference":
            skipped += 1
            continue
        session.add(
            BenchmarkDefinition(
                release_id=release.id,
                claim_id=claim.id,
                breed_external_id=claim.breed_external_id,
                variety_external_id=claim.variety_external_id,
                measurement_type=(
                    "weight"
                    if claim.claim_type == "adult_weight_reference"
                    else "height_at_withers"
                ),
                unit=expected_unit,
                reference_purpose="registry_conformation",
                minimum_value=Decimal(str(minimum)),
                maximum_value=Decimal(str(maximum)),
                minimum_age_days=None,
                maximum_age_days=None,
                life_stage="adult",
                sex_scope="combined",
                neuter_scope="any",
                population_geography=str(
                    record.get("population_geography") or "registry_standard"
                ),
                measurement_definition_fa=str(
                    record.get("measurement_definition")
                    or "مرجع ثبتی نژاد؛ معیار سلامت یا مقدار ایده‌آل فردی نیست."
                ),
                comparison_allowed=False,
                status="active",
                recorded_by_operator_id=operator_id,
            )
        )
        created += 1
    return {"candidates": len(claims), "created": created, "skipped": skipped}
