from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentIdentity
from app.db.session import get_db_session
from app.modules.households.models import Household, HouseholdMembership
from app.modules.identity.privacy import PrivacyRequest
from app.modules.inventory.models import InventoryUnit
from app.modules.orders.models import Order
from app.modules.pet_health.models import (
    BodyAssessment,
    BodyAssessmentAsset,
    HealthMeasurement,
    MeasurementReminder,
    PetAsset,
    PetConsent,
)
from app.modules.pets.models import Pet

router = APIRouter(prefix="/privacy", tags=["privacy"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]


class PrivacyRequestBody(BaseModel):
    request_type: str = Field(pattern=r"^(disable|anonymize)$")
    reason: str | None = Field(default=None, max_length=2000)


class PrivacyRequestResponse(BaseModel):
    id: UUID
    status: str


@router.get("/export", response_model=dict[str, object])
async def export_my_data(
    identity: CurrentIdentity, session: SessionDependency
) -> dict[str, object]:
    memberships = list(
        (
            await session.scalars(
                select(HouseholdMembership).where(
                    HouseholdMembership.identity_id == identity.id
                )
            )
        ).all()
    )
    household_ids = [item.household_id for item in memberships]
    households = list(
        (await session.scalars(select(Household).where(Household.id.in_(household_ids)))).all()
    )
    pets = list(
        (await session.scalars(select(Pet).where(Pet.household_id.in_(household_ids)))).all()
    )
    orders = list(
        (await session.scalars(select(Order).where(Order.household_id.in_(household_ids)))).all()
    )
    inventory = list(
        (
            await session.scalars(
                select(InventoryUnit).where(InventoryUnit.household_id.in_(household_ids))
            )
        ).all()
    )
    pet_ids = [item.id for item in pets]
    measurements = list(
        (
            await session.scalars(
                select(HealthMeasurement).where(HealthMeasurement.pet_id.in_(pet_ids))
            )
        ).all()
    )
    reminders = list(
        (
            await session.scalars(
                select(MeasurementReminder).where(MeasurementReminder.pet_id.in_(pet_ids))
            )
        ).all()
    )
    consents = list(
        (await session.scalars(select(PetConsent).where(PetConsent.pet_id.in_(pet_ids)))).all()
    )
    assets = list(
        (await session.scalars(select(PetAsset).where(PetAsset.pet_id.in_(pet_ids)))).all()
    )
    assessments = list(
        (
            await session.scalars(
                select(BodyAssessment).where(BodyAssessment.pet_id.in_(pet_ids))
            )
        ).all()
    )
    assessment_ids = [item.id for item in assessments]
    assessment_assets = list(
        (
            await session.scalars(
                select(BodyAssessmentAsset).where(
                    BodyAssessmentAsset.assessment_id.in_(assessment_ids)
                )
            )
        ).all()
    )
    return {
        "identity": {
            "id": identity.id,
            "mobile_e164": identity.mobile_e164,
            "status": identity.status,
            "created_at": identity.created_at,
        },
        "households": [{"id": item.id, "name": item.name} for item in households],
        "pets": [
            {
                "id": item.id,
                "household_id": item.household_id,
                "name": item.name,
                "species": item.species,
                "birth_date": item.birth_date,
                "birth_date_precision": item.birth_date_precision,
                "sex": item.sex,
                "neuter_status": item.neuter_status,
                "expected_adult_size": item.expected_adult_size,
                "breed_reference_id": item.breed_reference_id,
                "breed_variety_id": item.breed_variety_id,
                "breed_identification_source": item.breed_identification_source,
                "mixed_breed": item.mixed_breed,
                "reproductive_state": item.reproductive_state,
            }
            for item in pets
        ],
        "orders": [
            {
                "id": item.id,
                "household_id": item.household_id,
                "status": item.status,
                "currency": item.currency,
                "merchandise_total_irr": item.merchandise_total_irr,
                "created_at": item.created_at,
            }
            for item in orders
        ],
        "inventory": [
            {
                "id": item.id,
                "household_id": item.household_id,
                "label": item.label,
                "source": item.source,
                "state": item.state,
            }
            for item in inventory
        ],
        "health_measurements": [
            {
                "id": item.id,
                "pet_id": item.pet_id,
                "measurement_type": item.measurement_type,
                "value": item.value,
                "unit": item.unit,
                "measured_at": item.measured_at,
                "source": item.source,
                "measurement_method": item.measurement_method,
                "confidence": item.confidence,
                "notes": item.notes,
                "status": item.status,
                "supersedes_measurement_id": item.supersedes_measurement_id,
                "correction_reason": item.correction_reason,
            }
            for item in measurements
        ],
        "measurement_reminders": [
            {
                "id": item.id,
                "pet_id": item.pet_id,
                "measurement_type": item.measurement_type,
                "due_at": item.due_at,
                "status": item.status,
                "completed_at": item.completed_at,
                "dismissed_at": item.dismissed_at,
            }
            for item in reminders
        ],
        "pet_consents": [
            {
                "id": item.id,
                "pet_id": item.pet_id,
                "purpose": item.purpose,
                "policy_version": item.policy_version,
                "status": item.status,
                "granted_at": item.granted_at,
                "withdrawn_at": item.withdrawn_at,
            }
            for item in consents
        ],
        "pet_assets": [
            {
                "id": item.id,
                "pet_id": item.pet_id,
                "consent_id": item.consent_id,
                "category": item.category,
                "purpose": item.purpose,
                "original_filename": item.original_filename,
                "media_type": item.media_type,
                "size_bytes": item.size_bytes,
                "checksum_sha256": item.checksum_sha256,
                "captured_at": item.captured_at,
                "status": item.status,
                "removed_at": item.removed_at,
            }
            for item in assets
        ],
        "body_assessments": [
            {
                "id": item.id,
                "pet_id": item.pet_id,
                "bcs_score": item.bcs_score,
                "bcs_scale": item.bcs_scale,
                "muscle_condition": item.muscle_condition,
                "assessment_source": item.assessment_source,
                "answers": item.answers,
                "assessed_at": item.assessed_at,
                "status": item.status,
                "veterinarian_name": item.veterinarian_name,
                "veterinarian_credential": item.veterinarian_credential,
                "veterinarian_confirmed_at": item.veterinarian_confirmed_at,
                "confirmation_evidence_file_id": item.confirmation_evidence_file_id,
            }
            for item in assessments
        ],
        "body_assessment_assets": [
            {
                "assessment_id": item.assessment_id,
                "asset_id": item.asset_id,
                "role": item.role,
            }
            for item in assessment_assets
        ],
    }


@router.post(
    "/requests",
    response_model=PrivacyRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_privacy_action(
    body: PrivacyRequestBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> PrivacyRequestResponse:
    existing = await session.scalar(
        select(PrivacyRequest).where(
            PrivacyRequest.identity_id == identity.id,
            PrivacyRequest.request_type == body.request_type,
            PrivacyRequest.status.in_(("requested", "awaiting_policy")),
        )
    )
    if existing is not None:
        return PrivacyRequestResponse(id=existing.id, status=existing.status)
    request = PrivacyRequest(
        identity_id=identity.id,
        request_type=body.request_type,
        status="requested" if body.request_type == "disable" else "awaiting_policy",
        reason=body.reason,
    )
    session.add(request)
    await session.commit()
    return PrivacyRequestResponse(id=request.id, status=request.status)
