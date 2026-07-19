from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentIdentity
from app.common.time import utc_now
from app.db.session import get_db_session
from app.modules.households.access import HouseholdAccessError, require_pet_access
from app.modules.pet_health.benchmarks import BenchmarkInput, BenchmarkRule, evaluate_benchmark
from app.modules.pet_health.models import (
    BenchmarkDefinition,
    HealthMeasurement,
    MeasurementReminder,
)
from app.modules.pet_knowledge.guidance import eligible_guidance, public_guidance_item
from app.modules.pet_knowledge.models import (
    KnowledgeBreed,
    KnowledgeClaim,
    KnowledgeGuidance,
    KnowledgeGuidancePreference,
    KnowledgeRelease,
    KnowledgeVariety,
)
from app.modules.pets.models import Pet, PetBreedSelection

router = APIRouter(prefix="/pet-life", tags=["pet-health"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]

_UNITS = {
    "weight": {"kg", "g"},
    "height_at_withers": {"cm"},
    "chest_circumference": {"cm"},
    "body_length": {"cm"},
    "temperature": {"celsius"},
    "resting_respiratory_rate": {"breaths_per_minute"},
}


class PetProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    birth_date: date | None = None
    birth_date_precision: str | None = Field(
        default=None, pattern=r"^(exact|month|year|estimated)$"
    )
    sex: str | None = Field(default=None, pattern=r"^(female|male|unknown)$")
    neuter_status: str | None = Field(default=None, pattern=r"^(intact|neutered|unknown)$")
    expected_adult_size: str | None = Field(
        default=None, pattern=r"^(very_small|small|medium|large|giant|unknown)$"
    )
    breed_reference_id: str | None = Field(default=None, max_length=150)
    breed_variety_id: str | None = Field(default=None, max_length=150)
    breed_identification_source: str | None = Field(
        default=None,
        pattern=(
            r"^(owner_reported|veterinarian_reported|registry_confirmed|dna_estimated|unknown)$"
        ),
    )
    mixed_breed: bool | None = None
    reproductive_state: str | None = Field(
        default=None, pattern=r"^(not_applicable|pregnant|lactating|unknown)$"
    )


class MeasurementBody(BaseModel):
    measurement_type: str = Field(pattern="^(" + "|".join(_UNITS) + ")$")
    value: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit: str = Field(min_length=1, max_length=30)
    measured_at: datetime
    source: str = Field(pattern=r"^(owner_reported|veterinarian_reported|device_import)$")
    measurement_method: str | None = Field(default=None, max_length=100)
    confidence: str = Field(default="medium", pattern=r"^(low|medium|high)$")
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_unit(self) -> MeasurementBody:
        if self.unit not in _UNITS[self.measurement_type]:
            raise ValueError("unit is not valid for measurement type")
        return self


class CorrectionBody(MeasurementBody):
    correction_reason: str = Field(min_length=3, max_length=2000)


class ReminderBody(BaseModel):
    measurement_type: str = Field(pattern=r"^(weight|body_condition)$")
    due_at: datetime


class BreedSelectionBody(BaseModel):
    selection_mode: str = Field(pattern=r"^(known|mixed|unknown)$")
    breed_reference_id: str | None = Field(default=None, max_length=150)
    breed_variety_id: str | None = Field(default=None, max_length=150)
    identification_source: str = Field(
        default="owner_reported",
        pattern=(
            r"^(owner_reported|veterinarian_reported|registry_confirmed|dna_estimated|unknown)$"
        ),
    )

    @model_validator(mode="after")
    def validate_selection(self) -> BreedSelectionBody:
        if self.selection_mode == "known" and self.breed_reference_id is None:
            raise ValueError("known selection requires breed")
        if self.selection_mode != "known" and (
            self.breed_reference_id is not None or self.breed_variety_id is not None
        ):
            raise ValueError("mixed or unknown selection cannot assign one breed")
        if self.breed_variety_id is not None and self.breed_reference_id is None:
            raise ValueError("variety requires breed")
        return self


class GuidancePreferenceBody(BaseModel):
    action: str = Field(pattern=r"^(dismiss|snooze|restore)$")
    snoozed_until: datetime | None = None

    @model_validator(mode="after")
    def validate_action(self) -> GuidancePreferenceBody:
        if self.action == "snooze" and self.snoozed_until is None:
            raise ValueError("snooze requires snoozed_until")
        if self.action != "snooze" and self.snoozed_until is not None:
            raise ValueError("only snooze accepts snoozed_until")
        return self


class PetProfileResponse(BaseModel):
    id: UUID
    household_id: UUID
    name: str
    species: str
    birth_date: date | None = None
    birth_date_precision: str | None = None
    sex: str | None = None
    neuter_status: str | None = None
    expected_adult_size: str | None = None
    breed_reference_id: str | None = None
    breed_variety_id: str | None = None
    breed_identification_source: str | None = None
    mixed_breed: bool | None = None
    breed_selection_mode: str | None = None
    reproductive_state: str | None = None
    status: str


class BreedSelectionResponse(BaseModel):
    selection_id: UUID
    release_version: str
    profile: PetProfileResponse


class BreedSelectionHistoryItem(BaseModel):
    id: UUID
    selection_mode: str
    breed_reference_id: str | None = None
    breed_variety_id: str | None = None
    identification_source: str
    knowledge_release_id: UUID
    selected_at: datetime


class ProfileCompletenessResponse(BaseModel):
    completed_fields: list[str]
    missing_fields: list[str]
    next_prompt: str | None = None
    completion_percent: int
    guardrail: Literal["optional_progressive_profile"] = "optional_progressive_profile"


class CareGuidanceReleaseSummary(BaseModel):
    dataset_version: str
    checksum_sha256: str


class CareGuidanceItemResponse(BaseModel):
    id: UUID
    external_id: str
    domain: str
    text_fa: str
    population_level_explanation_fa: str | None = None
    professional_discussion_fa: str | None = None
    emergency_classification: str
    supporting_claim_ids: list[str]
    release: CareGuidanceReleaseSummary
    reviewer_disclosure: str
    interpretation: Literal["general_care_guidance_not_individual_medical_advice"] = (
        "general_care_guidance_not_individual_medical_advice"
    )


class CareGuidanceResponse(BaseModel):
    state: Literal[
        "breed_specific_guidance_unavailable", "no_eligible_guidance", "available"
    ]
    items: list[CareGuidanceItemResponse]
    disclaimer_fa: str


class MeasurementMutationResponse(BaseModel):
    id: UUID
    status: str


class MeasurementItemResponse(BaseModel):
    id: UUID
    measurement_type: str
    value: float
    unit: str
    measured_at: datetime
    source: str
    measurement_method: str | None = None
    confidence: str
    notes: str | None = None
    status: str
    supersedes_measurement_id: UUID | None = None
    correction_reason: str | None = None


class ReferenceRange(BaseModel):
    minimum: float
    maximum: float
    unit: str


class ReferenceComparisonItem(BaseModel):
    benchmark_id: UUID
    claim_id: str
    claim_text_fa: str
    release_version: str
    reference_purpose: str
    reference_range: ReferenceRange
    population_geography: str | None = None
    measurement_definition_fa: str | None = None
    state: Literal["not_applicable", "reference_only", "compared"]
    reasons: list[str]
    classification: Literal["below_reference", "above_reference", "within_reference"] | None = None
    age_days: int | None = None
    normalized_value: float | None = None
    interpretation: Literal["non_diagnostic_population_reference"] | None = None


class ReferenceComparisonResponse(BaseModel):
    measurement_id: UUID
    state: Literal["available", "no_applicable_reference"]
    items: list[ReferenceComparisonItem]
    disclaimer_fa: str


class WeightTrendChangeWindow(BaseModel):
    baseline_weight_kg: float
    change_percent: float


class WeightTrendUnavailable(BaseModel):
    state: Literal["no_measurements"] = "no_measurements"
    current_weight_kg: None = None
    changes: dict[str, object] = Field(default_factory=dict)


class WeightTrendAvailable(BaseModel):
    state: Literal["available"] = "available"
    current_weight_kg: float
    measured_at: datetime
    changes: dict[str, WeightTrendChangeWindow | None]
    interpretation: Literal["personal_trend_only"] = "personal_trend_only"


WeightTrendResult = Annotated[
    WeightTrendUnavailable | WeightTrendAvailable, Field(discriminator="state")
]


class ReminderMutationResponse(BaseModel):
    id: UUID
    status: str


async def _pet(session: AsyncSession, identity_id: UUID, pet_id: UUID) -> Pet:
    try:
        return await require_pet_access(session, identity_id=identity_id, pet_id=pet_id)
    except HouseholdAccessError as exc:
        raise HTTPException(status_code=404, detail="pet_not_found") from exc


def _profile(pet: Pet) -> PetProfileResponse:
    return PetProfileResponse(
        id=pet.id,
        household_id=pet.household_id,
        name=pet.name,
        species=pet.species,
        birth_date=pet.birth_date,
        birth_date_precision=pet.birth_date_precision,
        sex=pet.sex,
        neuter_status=pet.neuter_status,
        expected_adult_size=pet.expected_adult_size,
        breed_reference_id=pet.breed_reference_id,
        breed_variety_id=pet.breed_variety_id,
        breed_identification_source=pet.breed_identification_source,
        mixed_breed=pet.mixed_breed,
        breed_selection_mode=pet.breed_selection_mode,
        reproductive_state=pet.reproductive_state,
        status=pet.status,
    )


@router.get("/pets/{pet_id}/profile", response_model=PetProfileResponse)
async def get_pet_profile(
    pet_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> PetProfileResponse:
    return _profile(await _pet(session, identity.id, pet_id))


@router.patch("/pets/{pet_id}/profile", response_model=PetProfileResponse)
async def update_pet_profile(
    pet_id: UUID,
    body: PetProfilePatch,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> PetProfileResponse:
    pet = await _pet(session, identity.id, pet_id)
    changes = body.model_dump(exclude_unset=True)
    if set(changes) & {
        "breed_reference_id",
        "breed_variety_id",
        "breed_identification_source",
        "mixed_breed",
    }:
        raise HTTPException(status_code=422, detail="use_breed_selection_endpoint")
    for field, value in changes.items():
        setattr(pet, field, value)
    await session.commit()
    return _profile(pet)


@router.put("/pets/{pet_id}/breed-selection", response_model=BreedSelectionResponse)
async def select_pet_breed(
    pet_id: UUID,
    body: BreedSelectionBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> BreedSelectionResponse:
    pet = await _pet(session, identity.id, pet_id)
    release = await session.scalar(
        select(KnowledgeRelease).where(KnowledgeRelease.status == "published").limit(1)
    )
    if release is None:
        raise HTTPException(status_code=409, detail="published_knowledge_required")
    if body.selection_mode == "known":
        breed = await session.scalar(
            select(KnowledgeBreed).where(
                KnowledgeBreed.release_id == release.id,
                KnowledgeBreed.external_id == body.breed_reference_id,
            )
        )
        if breed is None:
            raise HTTPException(status_code=422, detail="breed_not_in_current_release")
        if breed.species != pet.species:
            raise HTTPException(status_code=422, detail="breed_species_mismatch")
        if body.breed_variety_id is not None:
            variety = await session.scalar(
                select(KnowledgeVariety).where(
                    KnowledgeVariety.release_id == release.id,
                    KnowledgeVariety.external_id == body.breed_variety_id,
                    KnowledgeVariety.breed_external_id == breed.external_id,
                )
            )
            if variety is None:
                raise HTTPException(status_code=422, detail="variety_not_valid_for_breed")
        pet.breed_reference_id = breed.external_id
        pet.breed_variety_id = body.breed_variety_id
        pet.breed_identification_source = body.identification_source
        pet.mixed_breed = False
    else:
        pet.breed_reference_id = None
        pet.breed_variety_id = None
        pet.breed_identification_source = (
            "unknown" if body.selection_mode == "unknown" else body.identification_source
        )
        pet.mixed_breed = body.selection_mode == "mixed"
    selection = PetBreedSelection(
        pet_id=pet.id,
        knowledge_release_id=release.id,
        selection_mode=body.selection_mode,
        breed_reference_id=pet.breed_reference_id,
        breed_variety_id=pet.breed_variety_id,
        identification_source=pet.breed_identification_source or "unknown",
        selected_by_identity_id=identity.id,
        selected_at=utc_now(),
    )
    session.add(selection)
    pet.breed_selection_mode = body.selection_mode
    await session.commit()
    return BreedSelectionResponse(
        selection_id=selection.id,
        release_version=release.dataset_version,
        profile=_profile(pet),
    )


@router.get(
    "/pets/{pet_id}/breed-selection/history",
    response_model=list[BreedSelectionHistoryItem],
)
async def pet_breed_selection_history(
    pet_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> list[BreedSelectionHistoryItem]:
    await _pet(session, identity.id, pet_id)
    rows = list(
        (
            await session.scalars(
                select(PetBreedSelection)
                .where(PetBreedSelection.pet_id == pet_id)
                .order_by(PetBreedSelection.selected_at.desc())
                .limit(100)
            )
        ).all()
    )
    return [
        BreedSelectionHistoryItem(
            id=item.id,
            selection_mode=item.selection_mode,
            breed_reference_id=item.breed_reference_id,
            breed_variety_id=item.breed_variety_id,
            identification_source=item.identification_source,
            knowledge_release_id=item.knowledge_release_id,
            selected_at=item.selected_at,
        )
        for item in rows
    ]


@router.get(
    "/pets/{pet_id}/profile-completeness", response_model=ProfileCompletenessResponse
)
async def pet_profile_completeness(
    pet_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> ProfileCompletenessResponse:
    pet = await _pet(session, identity.id, pet_id)
    has_measurement = (
        await session.scalar(
            select(HealthMeasurement.id)
            .where(
                HealthMeasurement.pet_id == pet.id,
                HealthMeasurement.measurement_type == "weight",
                HealthMeasurement.status == "active",
            )
            .limit(1)
        )
        is not None
    )
    states = {
        "birth_date": pet.birth_date is not None,
        "sex": pet.sex is not None,
        "neuter_status": pet.neuter_status is not None,
        "breed_state": pet.breed_selection_mode is not None,
        "weight": has_measurement,
    }
    missing = [field for field, complete in states.items() if not complete]
    return ProfileCompletenessResponse(
        completed_fields=[field for field, complete in states.items() if complete],
        missing_fields=missing,
        next_prompt=missing[0] if missing else None,
        completion_percent=round(sum(states.values()) / len(states) * 100),
    )


@router.get("/pets/{pet_id}/care-guidance", response_model=CareGuidanceResponse)
async def pet_care_guidance(
    pet_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
    domain: Annotated[
        str | None, Query(pattern=r"^(exercise|grooming|training|home|safety)$")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> CareGuidanceResponse:
    pet = await _pet(session, identity.id, pet_id)
    release, rows = await eligible_guidance(session, pet=pet, domain=domain)
    if release is None:
        return CareGuidanceResponse(
            state="breed_specific_guidance_unavailable",
            items=[],
            disclaimer_fa="راهنماهای عمومی جایگزین توصیه اختصاصی دامپزشک نیستند.",
        )
    return CareGuidanceResponse(
        state="available" if rows else "no_eligible_guidance",
        items=[
            CareGuidanceItemResponse.model_validate(public_guidance_item(item, release))
            for item in rows[:limit]
        ],
        disclaimer_fa="راهنماهای عمومی جایگزین توصیه اختصاصی دامپزشک نیستند.",
    )


@router.put(
    "/pets/{pet_id}/care-guidance/{guidance_id}/preference",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def set_care_guidance_preference(
    pet_id: UUID,
    guidance_id: UUID,
    body: GuidancePreferenceBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> None:
    pet = await _pet(session, identity.id, pet_id)
    guidance = await session.get(KnowledgeGuidance, guidance_id)
    if guidance is None:
        raise HTTPException(status_code=404, detail="care_guidance_not_found")
    release = await session.get(KnowledgeRelease, guidance.release_id)
    if (
        release is None
        or release.status != "published"
        or guidance.review_status != "veterinary_approved"
        or not guidance.app_eligible
        or guidance.breed_external_id != pet.breed_reference_id
        or (
            guidance.variety_external_id is not None
            and guidance.variety_external_id != pet.breed_variety_id
        )
    ):
        raise HTTPException(status_code=404, detail="care_guidance_not_found")
    preference = await session.scalar(
        select(KnowledgeGuidancePreference).where(
            KnowledgeGuidancePreference.pet_id == pet.id,
            KnowledgeGuidancePreference.guidance_id == guidance.id,
        )
    )
    if body.action == "restore":
        if preference is not None:
            await session.delete(preference)
        await session.commit()
        return
    if body.action == "snooze":
        assert body.snoozed_until is not None
        now = utc_now()
        if body.snoozed_until <= now:
            raise HTTPException(status_code=422, detail="snooze_must_be_in_future")
        if body.snoozed_until > now + timedelta(days=365):
            raise HTTPException(status_code=422, detail="snooze_too_long")
    if preference is None:
        preference = KnowledgeGuidancePreference(
            pet_id=pet.id,
            guidance_id=guidance.id,
            status="dismissed",
            snoozed_until=None,
            acted_by_identity_id=identity.id,
        )
        session.add(preference)
    preference.status = "snoozed" if body.action == "snooze" else "dismissed"
    preference.snoozed_until = body.snoozed_until if body.action == "snooze" else None
    preference.acted_by_identity_id = identity.id
    await session.commit()


@router.post(
    "/pets/{pet_id}/measurements",
    response_model=MeasurementMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_measurement(
    pet_id: UUID,
    body: MeasurementBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> MeasurementMutationResponse:
    await _pet(session, identity.id, pet_id)
    if body.measured_at > utc_now():
        raise HTTPException(status_code=422, detail="measurement_cannot_be_in_future")
    if body.source != "owner_reported":
        raise HTTPException(status_code=422, detail="professional_or_device_provenance_required")
    measurement = HealthMeasurement(
        pet_id=pet_id,
        entered_by_identity_id=identity.id,
        status="active",
        **body.model_dump(),
    )
    session.add(measurement)
    await session.commit()
    return MeasurementMutationResponse(id=measurement.id, status=measurement.status)


@router.post(
    "/pets/{pet_id}/measurements/{measurement_id}/corrections",
    response_model=MeasurementMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def correct_measurement(
    pet_id: UUID,
    measurement_id: UUID,
    body: CorrectionBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> MeasurementMutationResponse:
    await _pet(session, identity.id, pet_id)
    original = await session.get(HealthMeasurement, measurement_id, with_for_update=True)
    if original is None or original.pet_id != pet_id:
        raise HTTPException(status_code=404, detail="measurement_not_found")
    if original.status != "active":
        raise HTTPException(status_code=409, detail="measurement_already_corrected")
    if body.measurement_type != original.measurement_type:
        raise HTTPException(status_code=422, detail="correction_type_must_match_original")
    if body.measured_at > utc_now():
        raise HTTPException(status_code=422, detail="measurement_cannot_be_in_future")
    if body.source != "owner_reported":
        raise HTTPException(status_code=422, detail="professional_or_device_provenance_required")
    original.status = "corrected"
    values = body.model_dump()
    reason = values.pop("correction_reason")
    replacement = HealthMeasurement(
        pet_id=pet_id,
        entered_by_identity_id=identity.id,
        supersedes_measurement_id=original.id,
        correction_reason=reason,
        status="active",
        **values,
    )
    session.add(replacement)
    await session.commit()
    return MeasurementMutationResponse(id=replacement.id, status=replacement.status)


@router.get("/pets/{pet_id}/measurements", response_model=list[MeasurementItemResponse])
async def list_measurements(
    pet_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
    measurement_type: Annotated[str | None, Query()] = None,
    include_corrected: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[MeasurementItemResponse]:
    await _pet(session, identity.id, pet_id)
    query = select(HealthMeasurement).where(HealthMeasurement.pet_id == pet_id)
    if measurement_type is not None:
        query = query.where(HealthMeasurement.measurement_type == measurement_type)
    if not include_corrected:
        query = query.where(HealthMeasurement.status == "active")
    rows = list(
        (await session.scalars(query.order_by(HealthMeasurement.measured_at).limit(limit))).all()
    )
    return [_measurement_item(item) for item in rows]


@router.get(
    "/pets/{pet_id}/measurements/{measurement_id}/reference-comparison",
    response_model=ReferenceComparisonResponse,
)
async def measurement_reference_comparison(
    pet_id: UUID,
    measurement_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> ReferenceComparisonResponse:
    pet = await _pet(session, identity.id, pet_id)
    measurement = await session.get(HealthMeasurement, measurement_id)
    if (
        measurement is None
        or measurement.pet_id != pet.id
        or measurement.status != "active"
    ):
        raise HTTPException(status_code=404, detail="active_measurement_not_found")
    rows = (
        await session.execute(
            select(BenchmarkDefinition, KnowledgeClaim, KnowledgeRelease)
            .join(KnowledgeClaim, KnowledgeClaim.id == BenchmarkDefinition.claim_id)
            .join(KnowledgeRelease, KnowledgeRelease.id == BenchmarkDefinition.release_id)
            .where(
                BenchmarkDefinition.status == "active",
                BenchmarkDefinition.measurement_type == measurement.measurement_type,
                BenchmarkDefinition.breed_external_id == pet.breed_reference_id,
                KnowledgeClaim.review_status == "veterinary_approved",
                KnowledgeClaim.app_eligible.is_(True),
                KnowledgeRelease.status == "published",
            )
            .order_by(BenchmarkDefinition.created_at)
        )
    ).all()
    items: list[ReferenceComparisonItem] = []
    for benchmark, claim, release in rows:
        result = evaluate_benchmark(
            BenchmarkInput(
                value=measurement.value,
                unit=measurement.unit,
                measured_on=measurement.measured_at.date(),
                pet_birth_date=pet.birth_date,
                pet_birth_date_precision=pet.birth_date_precision,
                pet_sex=pet.sex,
                pet_neuter_status=pet.neuter_status,
                pet_breed_id=pet.breed_reference_id,
                pet_variety_id=pet.breed_variety_id,
                pet_mixed_breed=pet.mixed_breed,
            ),
            BenchmarkRule(
                unit=benchmark.unit,
                breed_id=benchmark.breed_external_id,
                variety_id=benchmark.variety_external_id,
                minimum=benchmark.minimum_value,
                maximum=benchmark.maximum_value,
                minimum_age_days=benchmark.minimum_age_days,
                maximum_age_days=benchmark.maximum_age_days,
                sex_scope=benchmark.sex_scope,
                neuter_scope=benchmark.neuter_scope,
                comparison_allowed=benchmark.comparison_allowed,
                reference_purpose=benchmark.reference_purpose,
            ),
        )
        items.append(
            ReferenceComparisonItem.model_validate(
                {
                    "benchmark_id": benchmark.id,
                    "claim_id": claim.external_id,
                    "claim_text_fa": claim.text_fa,
                    "release_version": release.dataset_version,
                    "reference_purpose": benchmark.reference_purpose,
                    "reference_range": {
                        "minimum": float(benchmark.minimum_value),
                        "maximum": float(benchmark.maximum_value),
                        "unit": benchmark.unit,
                    },
                    "population_geography": benchmark.population_geography,
                    "measurement_definition_fa": benchmark.measurement_definition_fa,
                    **result,
                }
            )
        )
    return ReferenceComparisonResponse(
        measurement_id=measurement.id,
        state="available" if items else "no_applicable_reference",
        items=items,
        disclaimer_fa=(
            "این مقایسه تشخیص پزشکی یا تعیین وزن ایده‌آل نیست و باید همراه با وضعیت بدنی "
            "و نظر دامپزشک تفسیر شود."
        ),
    )


@router.get("/pets/{pet_id}/weight-trend", response_model=WeightTrendResult)
async def weight_trend(
    pet_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> WeightTrendUnavailable | WeightTrendAvailable:
    await _pet(session, identity.id, pet_id)
    rows = list(
        (
            await session.scalars(
                select(HealthMeasurement)
                .where(
                    HealthMeasurement.pet_id == pet_id,
                    HealthMeasurement.measurement_type == "weight",
                    HealthMeasurement.status == "active",
                )
                .order_by(HealthMeasurement.measured_at)
            )
        ).all()
    )
    normalized = [(item.measured_at, _weight_kg(item)) for item in rows]
    if not normalized:
        return WeightTrendUnavailable()
    current_at, current = normalized[-1]
    changes: dict[str, WeightTrendChangeWindow | None] = {}
    for days in (7, 30, 90):
        cutoff = current_at - timedelta(days=days)
        candidates = [value for measured_at, value in normalized if measured_at <= cutoff]
        baseline = candidates[-1] if candidates else None
        changes[f"{days}_days"] = (
            None
            if baseline is None
            else WeightTrendChangeWindow(
                baseline_weight_kg=float(baseline),
                change_percent=float(
                    ((current - baseline) / baseline * 100).quantize(Decimal("0.1"))
                ),
            )
        )
    return WeightTrendAvailable(
        current_weight_kg=float(current),
        measured_at=current_at,
        changes=changes,
    )


@router.post(
    "/pets/{pet_id}/measurement-reminders",
    response_model=ReminderMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_measurement_reminder(
    pet_id: UUID,
    body: ReminderBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> ReminderMutationResponse:
    await _pet(session, identity.id, pet_id)
    reminder = MeasurementReminder(
        pet_id=pet_id,
        measurement_type=body.measurement_type,
        due_at=body.due_at,
        status="scheduled",
        created_by_identity_id=identity.id,
    )
    session.add(reminder)
    await session.commit()
    return ReminderMutationResponse(id=reminder.id, status=reminder.status)


@router.post(
    "/pets/{pet_id}/measurement-reminders/{reminder_id}/{action}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def resolve_measurement_reminder(
    pet_id: UUID,
    reminder_id: UUID,
    action: str,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> None:
    await _pet(session, identity.id, pet_id)
    if action not in {"complete", "dismiss"}:
        raise HTTPException(status_code=422, detail="invalid_reminder_action")
    reminder = await session.get(MeasurementReminder, reminder_id, with_for_update=True)
    if reminder is None or reminder.pet_id != pet_id:
        raise HTTPException(status_code=404, detail="reminder_not_found")
    if reminder.status != "scheduled":
        raise HTTPException(status_code=409, detail="reminder_already_resolved")
    now = utc_now()
    if action == "complete":
        reminder.status = "completed"
        reminder.completed_at = now
    else:
        reminder.status = "dismissed"
        reminder.dismissed_at = now
    await session.commit()


def _measurement_item(item: HealthMeasurement) -> MeasurementItemResponse:
    return MeasurementItemResponse(
        id=item.id,
        measurement_type=item.measurement_type,
        value=float(item.value),
        unit=item.unit,
        measured_at=item.measured_at,
        source=item.source,
        measurement_method=item.measurement_method,
        confidence=item.confidence,
        notes=item.notes,
        status=item.status,
        supersedes_measurement_id=item.supersedes_measurement_id,
        correction_reason=item.correction_reason,
    )


def _weight_kg(item: HealthMeasurement) -> Decimal:
    return item.value / Decimal(1000) if item.unit == "g" else item.value
