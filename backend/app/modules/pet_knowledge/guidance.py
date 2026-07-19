from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.pet_knowledge.models import (
    KnowledgeGuidance,
    KnowledgeGuidancePreference,
    KnowledgeRelease,
)
from app.modules.pets.models import Pet

TODAY_DOMAINS = ("exercise", "grooming", "training", "home")


async def eligible_guidance(
    session: AsyncSession,
    *,
    pet: Pet,
    domain: str | None = None,
) -> tuple[KnowledgeRelease | None, list[KnowledgeGuidance]]:
    if pet.breed_selection_mode != "known" or pet.breed_reference_id is None:
        return None, []
    release = await session.scalar(
        select(KnowledgeRelease).where(KnowledgeRelease.status == "published").limit(1)
    )
    if release is None:
        return None, []
    query = select(KnowledgeGuidance).where(
        KnowledgeGuidance.release_id == release.id,
        KnowledgeGuidance.breed_external_id == pet.breed_reference_id,
        KnowledgeGuidance.review_status == "veterinary_approved",
        KnowledgeGuidance.app_eligible.is_(True),
    )
    if domain is not None:
        query = query.where(KnowledgeGuidance.domain == domain)
    rows = list(
        (
            await session.scalars(
                query.order_by(
                    KnowledgeGuidance.variety_external_id.desc().nullslast(),
                    KnowledgeGuidance.domain,
                    KnowledgeGuidance.external_id,
                )
            )
        ).all()
    )
    preferences = {
        item.guidance_id: item
        for item in (
            await session.scalars(
                select(KnowledgeGuidancePreference).where(
                    KnowledgeGuidancePreference.pet_id == pet.id
                )
            )
        ).all()
    }
    now = utc_now()
    eligible: list[KnowledgeGuidance] = []
    for item in rows:
        if (
            item.variety_external_id is not None
            and item.variety_external_id != pet.breed_variety_id
        ):
            continue
        preference = preferences.get(item.id)
        if preference is not None and (
            preference.status == "dismissed"
            or (
                preference.status == "snoozed"
                and preference.snoozed_until is not None
                and preference.snoozed_until > now
            )
        ):
            continue
        if not guidance_age_applicable(item.record, pet.birth_date, now.date()):
            continue
        eligible.append(item)
    return release, eligible


def guidance_age_applicable(
    record: dict[str, object], birth_date: date | None, on_date: date
) -> bool:
    minimum = record.get("minimum_age_days")
    maximum = record.get("maximum_age_days")
    if minimum is None and maximum is None:
        return True
    if birth_date is None:
        return False
    age_days = (on_date - birth_date).days
    if age_days < 0:
        return False
    if isinstance(minimum, int) and age_days < minimum:
        return False
    if isinstance(maximum, int) and age_days > maximum:
        return False
    return True


def public_guidance_item(
    guidance: KnowledgeGuidance, release: KnowledgeRelease
) -> dict[str, Any]:
    record = guidance.record
    return {
        "id": guidance.id,
        "external_id": guidance.external_id,
        "domain": guidance.domain,
        "text_fa": guidance.text_fa,
        "population_level_explanation_fa": record.get("population_level_explanation_fa"),
        "professional_discussion_fa": record.get("professional_discussion_fa"),
        "emergency_classification": record.get("emergency_classification", "not_emergency"),
        "supporting_claim_ids": guidance.supporting_claim_external_ids,
        "release": {
            "dataset_version": release.dataset_version,
            "checksum_sha256": release.checksum_sha256,
        },
        "reviewer_disclosure": "anonymous_external_veterinarian",
        "interpretation": "general_care_guidance_not_individual_medical_advice",
    }


async def today_guidance(
    session: AsyncSession, *, pet: Pet
) -> dict[str, Any] | None:
    release, rows = await eligible_guidance(session, pet=pet)
    if release is None:
        return None
    item = next((row for row in rows if row.domain in TODAY_DOMAINS), None)
    return public_guidance_item(item, release) if item is not None else None
