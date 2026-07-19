from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentIdentity
from app.db.session import get_db_session
from app.modules.households.access import HouseholdAccessError, require_pet_access
from app.modules.pet_knowledge.models import (
    KnowledgeBreed,
    KnowledgeClaim,
    KnowledgeClaimSource,
    KnowledgeGuidance,
    KnowledgeRelease,
    KnowledgeSource,
    KnowledgeVariety,
)
from app.modules.pet_knowledge.search import rank_breed_match
from app.modules.pets.models import Pet

router = APIRouter(prefix="/knowledge", tags=["pet-knowledge"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]


class ReleaseSummary(BaseModel):
    dataset_version: str
    checksum_sha256: str
    published_at: datetime


class BreedSummary(BaseModel):
    id: str
    species: Literal["dog", "cat"]
    name_fa: str
    name_en: str


class BreedListResponse(BaseModel):
    release: ReleaseSummary | None
    items: list[BreedSummary]


class BreedSearchItem(BreedSummary):
    aliases_fa: list[str]
    matched_field: str


class BreedSearchReleaseSummary(BaseModel):
    dataset_version: str


class BreedSearchResponse(BaseModel):
    release: BreedSearchReleaseSummary | None
    items: list[BreedSearchItem]


class KnowledgeSourceItem(BaseModel):
    id: str
    type: str
    title: str
    url: str | None = None
    doi: str | None = None
    pmid: str | None = None
    publication_date: str | None = None
    retrieved_at: str | None = None
    retrieval_date: str | None = None


class KnowledgeClaimItem(BaseModel):
    id: str
    claim_type: str
    text_fa: str
    variety_id: str | None
    review_status: str
    reviewer_disclosure: str
    sources: list[KnowledgeSourceItem]


class BreedVarietyItem(BaseModel):
    id: str
    name_fa: str
    name_en: str


class KnowledgeGuidanceItem(BaseModel):
    id: str
    domain: str
    text_fa: str
    variety_id: str | None
    supporting_claim_ids: list[str]
    reviewer_disclosure: str


class BreedDetailResponse(BaseModel):
    release: ReleaseSummary
    breed: BreedSummary
    varieties: list[BreedVarietyItem]
    claims: list[KnowledgeClaimItem]
    guidance: list[KnowledgeGuidanceItem]


class PetKnowledgeUnavailable(BaseModel):
    pet_id: UUID
    status: Literal["breed_not_recorded"] = "breed_not_recorded"
    claims: list[KnowledgeClaimItem] = Field(default_factory=list)
    disclaimer_fa: str


class PetKnowledgeAvailable(BaseModel):
    pet_id: UUID
    status: Literal["available"] = "available"
    breed_identification_source: str | None
    release: ReleaseSummary
    breed: BreedSummary
    claims: list[KnowledgeClaimItem]
    guidance: list[KnowledgeGuidanceItem]
    disclaimer_fa: str


PetKnowledgeResult = Annotated[
    PetKnowledgeUnavailable | PetKnowledgeAvailable, Field(discriminator="status")
]


async def _current_release(session: AsyncSession) -> KnowledgeRelease | None:
    release: KnowledgeRelease | None = await session.scalar(
        select(KnowledgeRelease)
        .where(KnowledgeRelease.status == "published")
        .order_by(KnowledgeRelease.published_at.desc())
        .limit(1)
    )
    return release


@router.get("/breeds", response_model=BreedListResponse)
async def public_breeds(
    session: SessionDependency,
    species: Annotated[str | None, Query(pattern=r"^(dog|cat)$")] = None,
) -> BreedListResponse:
    release = await _current_release(session)
    if release is None:
        return BreedListResponse(release=None, items=[])
    query = select(KnowledgeBreed).where(KnowledgeBreed.release_id == release.id)
    if species is not None:
        query = query.where(KnowledgeBreed.species == species)
    breeds = list((await session.scalars(query.order_by(KnowledgeBreed.name_fa))).all())
    return BreedListResponse(
        release=ReleaseSummary(
            dataset_version=release.dataset_version,
            checksum_sha256=release.checksum_sha256,
            published_at=release.published_at,
        ),
        items=[
            BreedSummary(
                id=item.external_id,
                species=item.species,
                name_fa=item.name_fa,
                name_en=item.name_en,
            )
            for item in breeds
        ],
    )


@router.get("/search", response_model=BreedSearchResponse)
async def search_breeds(
    session: SessionDependency,
    q: Annotated[str, Query(min_length=1, max_length=100)],
    species: Annotated[str | None, Query(pattern=r"^(dog|cat)$")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> BreedSearchResponse:
    release = await _current_release(session)
    if release is None:
        return BreedSearchResponse(release=None, items=[])
    query = select(KnowledgeBreed).where(KnowledgeBreed.release_id == release.id)
    if species is not None:
        query = query.where(KnowledgeBreed.species == species)
    breeds = list((await session.scalars(query)).all())
    ranked: list[tuple[int, str, KnowledgeBreed, str]] = []
    for breed in breeds:
        aliases = _breed_aliases(breed)
        match = rank_breed_match(
            q, name_fa=breed.name_fa, name_en=breed.name_en, aliases_fa=aliases
        )
        if match is not None:
            ranked.append((match[0], breed.name_fa, breed, match[1]))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return BreedSearchResponse(
        release=BreedSearchReleaseSummary(dataset_version=release.dataset_version),
        items=[
            BreedSearchItem(
                id=breed.external_id,
                species=breed.species,
                name_fa=breed.name_fa,
                name_en=breed.name_en,
                aliases_fa=_breed_aliases(breed),
                matched_field=matched_field,
            )
            for _, _, breed, matched_field in ranked[:limit]
        ],
    )


def _breed_aliases(breed: KnowledgeBreed) -> list[str]:
    value = breed.record.get("aliases_fa")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


@router.get("/breeds/{breed_id:path}", response_model=BreedDetailResponse)
async def public_breed_detail(
    breed_id: str, session: SessionDependency
) -> BreedDetailResponse:
    release = await _current_release(session)
    if release is None:
        raise HTTPException(status_code=404, detail="published_knowledge_not_found")
    breed = await session.scalar(
        select(KnowledgeBreed).where(
            KnowledgeBreed.release_id == release.id,
            KnowledgeBreed.external_id == breed_id,
        )
    )
    if breed is None:
        raise HTTPException(status_code=404, detail="breed_not_found")
    varieties = list(
        (
            await session.scalars(
                select(KnowledgeVariety)
                .where(
                    KnowledgeVariety.release_id == release.id,
                    KnowledgeVariety.breed_external_id == breed.external_id,
                )
                .order_by(KnowledgeVariety.name_fa)
            )
        ).all()
    )
    claims = list(
        (
            await session.scalars(
                select(KnowledgeClaim)
                .where(
                    KnowledgeClaim.release_id == release.id,
                    KnowledgeClaim.breed_external_id == breed.external_id,
                    KnowledgeClaim.review_status == "veterinary_approved",
                    KnowledgeClaim.app_eligible.is_(True),
                )
                .order_by(KnowledgeClaim.claim_type, KnowledgeClaim.external_id)
            )
        ).all()
    )
    claim_items: list[KnowledgeClaimItem] = []
    for claim in claims:
        sources = list(
            (
                await session.scalars(
                    select(KnowledgeSource)
                    .join(
                        KnowledgeClaimSource,
                        KnowledgeClaimSource.source_id == KnowledgeSource.id,
                    )
                    .where(KnowledgeClaimSource.claim_id == claim.id)
                    .order_by(KnowledgeSource.external_id)
                )
            ).all()
        )
        claim_items.append(
            KnowledgeClaimItem(
                id=claim.external_id,
                claim_type=claim.claim_type,
                text_fa=claim.text_fa,
                variety_id=claim.variety_external_id,
                review_status="veterinary_approved",
                reviewer_disclosure="anonymous_external_veterinarian",
                sources=[_public_source(source) for source in sources],
            )
        )
    guidance = list(
        (
            await session.scalars(
                select(KnowledgeGuidance)
                .where(
                    KnowledgeGuidance.release_id == release.id,
                    KnowledgeGuidance.breed_external_id == breed.external_id,
                    KnowledgeGuidance.review_status == "veterinary_approved",
                    KnowledgeGuidance.app_eligible.is_(True),
                )
                .order_by(KnowledgeGuidance.domain, KnowledgeGuidance.external_id)
            )
        ).all()
    )
    return BreedDetailResponse(
        release=ReleaseSummary(
            dataset_version=release.dataset_version,
            checksum_sha256=release.checksum_sha256,
            published_at=release.published_at,
        ),
        breed=BreedSummary(
            id=breed.external_id,
            species=breed.species,
            name_fa=breed.name_fa,
            name_en=breed.name_en,
        ),
        varieties=[
            BreedVarietyItem(
                id=item.external_id,
                name_fa=item.name_fa,
                name_en=item.name_en,
            )
            for item in varieties
        ],
        claims=claim_items,
        guidance=[
            KnowledgeGuidanceItem(
                id=item.external_id,
                domain=item.domain,
                text_fa=item.text_fa,
                variety_id=item.variety_external_id,
                supporting_claim_ids=item.supporting_claim_external_ids,
                reviewer_disclosure="anonymous_external_veterinarian",
            )
            for item in guidance
        ],
    )


def _public_source(source: KnowledgeSource) -> KnowledgeSourceItem:
    allowed = {
        key: source.record.get(key)
        for key in (
            "url",
            "doi",
            "pmid",
            "publication_date",
            "retrieved_at",
            "retrieval_date",
        )
        if source.record.get(key) is not None
    }
    return KnowledgeSourceItem(
        id=source.external_id,
        type=source.source_type,
        title=source.title,
        **allowed,
    )


@router.get("/pets/{pet_id}", response_model=PetKnowledgeResult)
async def pet_knowledge(
    pet_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> PetKnowledgeUnavailable | PetKnowledgeAvailable:
    try:
        pet: Pet = await require_pet_access(session, identity_id=identity.id, pet_id=pet_id)
    except HouseholdAccessError as exc:
        raise HTTPException(status_code=404, detail="pet_not_found") from exc
    if pet.breed_reference_id is None:
        return PetKnowledgeUnavailable(
            pet_id=pet.id,
            disclaimer_fa="این اطلاعات عمومی است و جایگزین نظر دامپزشک نیست.",
        )
    detail = await public_breed_detail(pet.breed_reference_id, session)
    if detail.breed.species != pet.species:
        raise HTTPException(status_code=409, detail="pet_breed_species_mismatch")
    return PetKnowledgeAvailable(
        pet_id=pet.id,
        breed_identification_source=pet.breed_identification_source,
        release=detail.release,
        breed=detail.breed,
        claims=detail.claims,
        guidance=detail.guidance,
        disclaimer_fa="این اطلاعات عمومی است و جایگزین نظر دامپزشک نیست.",
    )
