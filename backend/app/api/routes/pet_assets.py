from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentIdentity
from app.common.time import utc_now
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.modules.households.access import HouseholdAccessError, require_pet_access
from app.modules.pet_health.models import (
    BodyAssessment,
    BodyAssessmentAsset,
    PetAsset,
    PetConsent,
)

router = APIRouter(prefix="/pet-life", tags=["pet-health-assets"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]

_CATEGORY_PURPOSE = {
    "body_top": "body_photographs",
    "body_side": "body_photographs",
    "medical_document": "medical_records",
    "lab_result": "medical_records",
    "other_medical": "medical_records",
}
_ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png"}


class ConsentBody(BaseModel):
    purpose: str = Field(pattern=r"^(body_photographs|medical_records)$")
    policy_version: str = Field(min_length=1, max_length=50)


class PetConsentResponse(BaseModel):
    id: UUID
    purpose: Literal["body_photographs", "medical_records"]
    policy_version: str
    status: Literal["granted", "withdrawn"]
    granted_at: datetime
    withdrawn_at: datetime | None = None


def _consent_response(consent: PetConsent) -> PetConsentResponse:
    return PetConsentResponse(
        id=consent.id,
        purpose=consent.purpose,
        policy_version=consent.policy_version,
        status=consent.status,
        granted_at=consent.granted_at,
        withdrawn_at=consent.withdrawn_at,
    )


class AssessmentAssetBody(BaseModel):
    asset_id: UUID
    role: str = Field(pattern=r"^(top|side|supporting)$")


class BodyAssessmentBody(BaseModel):
    bcs_score: int = Field(ge=1, le=9)
    bcs_scale: int = Field(default=9, ge=9, le=9)
    muscle_condition: str = Field(
        pattern=r"^(normal|mild_loss|moderate_loss|severe_loss|unknown)$"
    )
    answers: dict[str, object]
    assessed_at: datetime
    assets: list[AssessmentAssetBody] = Field(default_factory=list, max_length=10)


class PetAssetMutationResponse(BaseModel):
    id: UUID
    status: Literal["active"]


class PetAssetItemResponse(BaseModel):
    id: UUID
    category: Literal["body_top", "body_side", "medical_document", "lab_result", "other_medical"]
    purpose: Literal["body_photographs", "medical_records"]
    filename: str
    media_type: str
    size_bytes: int
    checksum_sha256: str
    captured_at: datetime | None = None
    created_at: datetime


class BodyAssessmentMutationResponse(BaseModel):
    id: UUID
    assessment_source: Literal["owner_reported"]


class BodyAssessmentItemResponse(BaseModel):
    id: UUID
    bcs_score: int
    bcs_scale: int
    muscle_condition: str
    assessment_source: str
    answers: dict[str, object]
    assessed_at: datetime
    veterinarian_name: str | None = None
    veterinarian_confirmed_at: datetime | None = None


async def _require_pet(session: AsyncSession, identity_id: UUID, pet_id: UUID) -> None:
    try:
        await require_pet_access(session, identity_id=identity_id, pet_id=pet_id)
    except HouseholdAccessError as exc:
        raise HTTPException(status_code=404, detail="pet_not_found") from exc


@router.get("/pets/{pet_id}/consents", response_model=list[PetConsentResponse])
async def list_pet_consents(
    pet_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> list[PetConsentResponse]:
    await _require_pet(session, identity.id, pet_id)
    consents = list(
        (
            await session.scalars(
                select(PetConsent)
                .where(PetConsent.pet_id == pet_id)
                .order_by(PetConsent.granted_at.desc())
            )
        ).all()
    )
    return [_consent_response(item) for item in consents]


@router.post(
    "/pets/{pet_id}/consents",
    response_model=PetConsentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_pet_consent(
    pet_id: UUID,
    body: ConsentBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> PetConsentResponse:
    await _require_pet(session, identity.id, pet_id)
    existing = await session.scalar(
        select(PetConsent).where(
            PetConsent.pet_id == pet_id,
            PetConsent.purpose == body.purpose,
            PetConsent.status == "granted",
        )
    )
    if existing is not None:
        if existing.policy_version != body.policy_version:
            raise HTTPException(
                status_code=409,
                detail="withdraw_existing_consent_before_policy_change",
            )
        return _consent_response(existing)
    consent = PetConsent(
        pet_id=pet_id,
        granted_by_identity_id=identity.id,
        purpose=body.purpose,
        policy_version=body.policy_version,
        status="granted",
        granted_at=utc_now(),
    )
    session.add(consent)
    await session.commit()
    return _consent_response(consent)


@router.post("/pets/{pet_id}/consents/{consent_id}/withdraw", status_code=204)
async def withdraw_pet_consent(
    pet_id: UUID,
    consent_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> None:
    await _require_pet(session, identity.id, pet_id)
    consent = await session.get(PetConsent, consent_id, with_for_update=True)
    if consent is None or consent.pet_id != pet_id:
        raise HTTPException(status_code=404, detail="consent_not_found")
    if consent.status == "withdrawn":
        return
    now = utc_now()
    consent.status = "withdrawn"
    consent.withdrawn_at = now
    await session.execute(
        update(PetAsset)
        .where(PetAsset.consent_id == consent.id, PetAsset.status == "active")
        .values(status="removed", removed_at=now)
    )
    await session.commit()


@router.post(
    "/pets/{pet_id}/assets",
    response_model=PetAssetMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_pet_asset(
    pet_id: UUID,
    request: Request,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
    filename: Annotated[str, Header(alias="X-Filename", min_length=1, max_length=300)],
    category: Annotated[
        str,
        Header(
            alias="X-Asset-Category",
            pattern=r"^(body_top|body_side|medical_document|lab_result|other_medical)$",
        ),
    ],
    consent_id: Annotated[UUID, Header(alias="X-Consent-ID")],
    captured_at: Annotated[datetime | None, Header(alias="X-Captured-At")] = None,
) -> PetAssetMutationResponse:
    await _require_pet(session, identity.id, pet_id)
    purpose = _CATEGORY_PURPOSE[category]
    consent = await session.get(PetConsent, consent_id)
    if (
        consent is None
        or consent.pet_id != pet_id
        or consent.purpose != purpose
        or consent.status != "granted"
    ):
        raise HTTPException(status_code=409, detail="active_matching_consent_required")
    media_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if media_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="unsupported_pet_asset_media_type")
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.pet_asset_max_bytes:
        raise HTTPException(status_code=413, detail="pet_asset_too_large")
    buffer = bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer) > settings.pet_asset_max_bytes:
            raise HTTPException(status_code=413, detail="pet_asset_too_large")
    content = bytes(buffer)
    if not content or not _matches_signature(content, media_type):
        raise HTTPException(status_code=422, detail="pet_asset_content_invalid")
    safe_name = _safe_filename(filename)
    key = f"pet-assets/{pet_id}/{uuid4()}/{safe_name}"
    from app.main import get_storage

    stored = await get_storage().put_bytes(key, content)
    asset = PetAsset(
        pet_id=pet_id,
        consent_id=consent.id,
        uploaded_by_identity_id=identity.id,
        category=category,
        purpose=purpose,
        storage_key=stored.key,
        original_filename=safe_name,
        media_type=media_type,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
        captured_at=captured_at,
        status="active",
    )
    session.add(asset)
    await session.commit()
    return PetAssetMutationResponse(id=asset.id, status=asset.status)


@router.get("/pets/{pet_id}/assets", response_model=list[PetAssetItemResponse])
async def list_pet_assets(
    pet_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> list[PetAssetItemResponse]:
    await _require_pet(session, identity.id, pet_id)
    assets = list(
        (
            await session.scalars(
                select(PetAsset)
                .where(PetAsset.pet_id == pet_id, PetAsset.status == "active")
                .order_by(PetAsset.created_at.desc())
                .limit(200)
            )
        ).all()
    )
    return [_asset_item(asset) for asset in assets]


@router.get("/pets/{pet_id}/assets/{asset_id}", response_class=FileResponse)
async def download_pet_asset(
    pet_id: UUID,
    asset_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> FileResponse:
    await _require_pet(session, identity.id, pet_id)
    asset = await session.get(PetAsset, asset_id)
    if asset is None or asset.pet_id != pet_id or asset.status != "active":
        raise HTTPException(status_code=404, detail="pet_asset_not_found")
    from app.main import get_storage

    path = get_storage().path_for(asset.storage_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="pet_asset_missing_from_storage")
    return FileResponse(path, media_type=asset.media_type, filename=asset.original_filename)


@router.delete("/pets/{pet_id}/assets/{asset_id}", status_code=204)
async def remove_pet_asset(
    pet_id: UUID,
    asset_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> None:
    await _require_pet(session, identity.id, pet_id)
    asset = await session.get(PetAsset, asset_id, with_for_update=True)
    if asset is None or asset.pet_id != pet_id:
        raise HTTPException(status_code=404, detail="pet_asset_not_found")
    if asset.status == "active":
        asset.status = "removed"
        asset.removed_at = utc_now()
        await session.commit()


@router.post(
    "/pets/{pet_id}/body-assessments",
    response_model=BodyAssessmentMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_body_assessment(
    pet_id: UUID,
    body: BodyAssessmentBody,
    identity: CurrentIdentity,
    session: SessionDependency,
) -> BodyAssessmentMutationResponse:
    await _require_pet(session, identity.id, pet_id)
    if body.assessed_at > utc_now():
        raise HTTPException(status_code=422, detail="assessment_cannot_be_in_future")
    if len({item.asset_id for item in body.assets}) != len(body.assets):
        raise HTTPException(status_code=422, detail="duplicate_assessment_asset")
    for link in body.assets:
        asset = await session.get(PetAsset, link.asset_id)
        if asset is None or asset.pet_id != pet_id or asset.status != "active":
            raise HTTPException(status_code=404, detail="assessment_asset_not_found")
        if asset.purpose != "body_photographs":
            raise HTTPException(status_code=422, detail="body_photo_required")
        if link.role == "top" and asset.category != "body_top":
            raise HTTPException(status_code=422, detail="top_photo_category_required")
        if link.role == "side" and asset.category != "body_side":
            raise HTTPException(status_code=422, detail="side_photo_category_required")
    assessment = BodyAssessment(
        pet_id=pet_id,
        bcs_score=body.bcs_score,
        bcs_scale=body.bcs_scale,
        muscle_condition=body.muscle_condition,
        assessment_source="owner_reported",
        answers=body.answers,
        assessed_at=body.assessed_at,
        entered_by_identity_id=identity.id,
        status="active",
    )
    session.add(assessment)
    await session.flush()
    for link in body.assets:
        session.add(
            BodyAssessmentAsset(
                assessment_id=assessment.id,
                asset_id=link.asset_id,
                role=link.role,
            )
        )
    await session.commit()
    return BodyAssessmentMutationResponse(
        id=assessment.id,
        assessment_source=assessment.assessment_source,
    )


@router.get(
    "/pets/{pet_id}/body-assessments", response_model=list[BodyAssessmentItemResponse]
)
async def list_body_assessments(
    pet_id: UUID, identity: CurrentIdentity, session: SessionDependency
) -> list[BodyAssessmentItemResponse]:
    await _require_pet(session, identity.id, pet_id)
    assessments = list(
        (
            await session.scalars(
                select(BodyAssessment)
                .where(BodyAssessment.pet_id == pet_id, BodyAssessment.status == "active")
                .order_by(BodyAssessment.assessed_at.desc())
                .limit(100)
            )
        ).all()
    )
    return [
        BodyAssessmentItemResponse(
            id=item.id,
            bcs_score=item.bcs_score,
            bcs_scale=item.bcs_scale,
            muscle_condition=item.muscle_condition,
            assessment_source=item.assessment_source,
            answers=item.answers,
            assessed_at=item.assessed_at,
            veterinarian_name=item.veterinarian_name,
            veterinarian_confirmed_at=item.veterinarian_confirmed_at,
        )
        for item in assessments
    ]


def _asset_item(asset: PetAsset) -> PetAssetItemResponse:
    return PetAssetItemResponse(
        id=asset.id,
        category=asset.category,
        purpose=asset.purpose,
        filename=asset.original_filename,
        media_type=asset.media_type,
        size_bytes=asset.size_bytes,
        checksum_sha256=asset.checksum_sha256,
        captured_at=asset.captured_at,
        created_at=asset.created_at,
    )


def _safe_filename(value: str) -> str:
    basename = value.replace("\\", "/").rsplit("/", 1)[-1]
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", basename).strip("._")
    if not safe:
        raise HTTPException(status_code=422, detail="invalid_pet_asset_filename")
    return safe[:200]


def _matches_signature(content: bytes, media_type: str) -> bool:
    if media_type == "application/pdf":
        return content.startswith(b"%PDF-")
    if media_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if media_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    return False
