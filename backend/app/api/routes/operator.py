import csv
import hashlib
import io
import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from string import Formatter
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.contracts import JourneyContentResponse, OrderCancellationResponse
from app.api.dependencies import CurrentOperator
from app.api.middleware import request_id_context
from app.common.time import add_months, utc_now
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.integrations.payment.factory import (
    PaymentProviderNotConfiguredError,
    build_payment_gateway,
)
from app.integrations.payment.zarinpal import ZarinpalError
from app.modules.catalog.availability import notify_available_subscribers
from app.modules.catalog.models import Offer, Product, ProductAlternative, Supplier
from app.modules.households.models import Household, HouseholdMembership
from app.modules.identity.models import AuthIdentity, AuthSession
from app.modules.identity.privacy import PrivacyRequest
from app.modules.inventory.models import InventoryUnit
from app.modules.inventory.projection import DeliveryProjectionError, project_delivered_order
from app.modules.journeys.content import valid_journey_content
from app.modules.journeys.models import JourneyDefinition, PetJourney
from app.modules.notifications.models import Notification, NotificationTemplate
from app.modules.orders.cancellation import OrderCancellation
from app.modules.orders.fulfillment import (
    FulfillmentTransitionError,
    apply_fulfillment_transition,
)
from app.modules.orders.models import Order, OrderLine
from app.modules.orders.refund_attestation import RefundAttestationError, attest_refund
from app.modules.orders.resolutions import OrderResolution
from app.modules.orders.shelf_life_exceptions import (
    ShelfLifeException,
    ShelfLifeExceptionError,
    propose_shelf_life_exception,
)
from app.modules.payments.models import PaymentAttempt
from app.modules.payments.service import PaymentService, PaymentWorkflowError
from app.modules.pet_health.models import BenchmarkDefinition, BodyAssessment
from app.modules.pet_knowledge.activation import (
    build_activation_preflight,
    execute_activation,
    rollback_activation,
)
from app.modules.pet_knowledge.models import (
    KnowledgeActivationRun,
    KnowledgeBreed,
    KnowledgeClaim,
    KnowledgeGuidance,
    KnowledgeRelease,
    KnowledgeReview,
    KnowledgeReviewTask,
    KnowledgeVariety,
)
from app.modules.pet_knowledge.service import (
    import_validated_bundle,
    materialize_release_benchmarks,
)
from app.modules.pet_knowledge.validation import canonical_bytes, validate_bundle
from app.modules.pets.models import Pet
from app.modules.purchasing.models import PurchaseBatch, PurchaseBatchAllocation, PurchaseBatchEvent
from app.modules.purchasing.service import PurchasingError, commit_batch
from app.modules.reporting.kpi import KPI_REGISTRY, KPIDefinition
from app.modules.reporting.service import KPIResult, compute_all_kpis, compute_kpi
from app.modules.reservations.models import Reservation
from app.modules.reservations.service import (
    ReservationError,
    operator_decline_reservation,
    reconfirm_and_propose_reservation,
)
from app.modules.sourcing.models import SourcingJob
from app.modules.system.audit import record_operator_action
from app.modules.system.models import OperatorAuditLog, OutboxEvent, WebhookInboxEvent
from app.modules.trust.files import EvidenceFile
from app.modules.trust.models import (
    ReferencePriceEvidence,
    SourcedUnitEvidence,
    SupplierAssurance,
)
from app.modules.wallet.models import WalletAccount, WalletCredit
from app.modules.wallet.service import WalletError, grant_late_delivery_credit

router = APIRouter(prefix="/operator", tags=["operator"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


class SupplierBody(BaseModel):
    internal_name: str = Field(min_length=1, max_length=200)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    reason: str = Field(min_length=5, max_length=1000)


class ProductBody(BaseModel):
    name_fa: str = Field(min_length=1, max_length=300)
    description_fa: str | None = Field(default=None, max_length=5000)
    reason: str = Field(min_length=5, max_length=1000)


class OfferBody(BaseModel):
    product_id: UUID
    supplier_id: UUID
    sku: str = Field(min_length=1, max_length=100)
    title_fa: str = Field(min_length=1, max_length=300)
    unit_label_fa: str = Field(min_length=1, max_length=100)
    price_irr: int = Field(gt=0)
    minimum_shelf_life_months: int = Field(default=6, ge=1, le=36)
    available_from: datetime | None = None
    available_until: datetime | None = None
    max_pending_quantity: int | None = Field(default=None, gt=0)
    reason: str = Field(min_length=5, max_length=1000)


class CreatedResponse(BaseModel):
    id: UUID


class ReconciliationResponse(BaseModel):
    state: str
    order_id: UUID


class ReconciliationBody(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class DeliverOrderBody(BaseModel):
    household_id: UUID
    reason: str = Field(min_length=5, max_length=1000)


class DeliveryResponse(BaseModel):
    inventory_unit_ids: list[UUID]


class FulfillmentBody(BaseModel):
    event_type: str = Field(
        pattern=r"^(sourcing_started|sourcing_failed|in_transit|delayed|cancelled)$"
    )
    reason: str = Field(min_length=5, max_length=2000)


class JourneyDefinitionBody(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    title_fa: str = Field(min_length=1, max_length=300)
    content: JourneyContentResponse
    reason: str = Field(min_length=5, max_length=1000)


class JourneyApprovalBody(BaseModel):
    approved_by: str = Field(min_length=3, max_length=200)
    reason: str = Field(min_length=5, max_length=1000)


def _journey_content_to_storage(content: JourneyContentResponse) -> dict[str, object]:
    return {
        "summary_fa": content.summary_fa,
        "duration_days": content.duration_days,
        "active_from": content.active_window.active_from.isoformat()
        if content.active_window.active_from
        else None,
        "active_until": content.active_window.active_until.isoformat()
        if content.active_window.active_until
        else None,
        "eligible_species": content.eligibility.eligible_species,
        "steps": [
            {
                "key": step.key,
                "title_fa": step.title_fa,
                "body_fa": step.body_fa,
                "allowed_answers": [
                    {"key": answer.key, "label_fa": answer.label_fa}
                    for answer in step.allowed_answers
                ],
            }
            for step in content.steps
        ],
        "completion_requires": content.completion_requirements.required_step_keys,
        "exception_behavior": {
            "behavior": content.exception_behavior.behavior,
            "message_fa": content.exception_behavior.message_fa,
        },
        "garden_object_key": content.garden_object_key,
        "professional_approval_ref": content.professional_approval_ref,
    }


class LateCreditBody(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class LateCreditResponse(BaseModel):
    credit_id: UUID
    amount_irr: int
    expires_at: datetime


class ResolutionBody(BaseModel):
    resolution_type: str = Field(pattern=r"^(refund|replacement|substitution)$")
    reason: str = Field(min_length=5, max_length=2000)
    proposed_facts: dict[str, object] = Field(default_factory=dict)


class SupplierAssuranceBody(BaseModel):
    version: int = Field(ge=1)
    evidence_file_id: UUID
    valid_from: date
    valid_until: date | None = None
    reason: str = Field(min_length=5, max_length=1000)


class ReferenceEvidenceBody(BaseModel):
    amount_irr: int = Field(gt=0)
    observed_at: datetime
    source_label: str = Field(min_length=1, max_length=300)
    evidence_file_id: UUID
    reason: str = Field(min_length=5, max_length=1000)


class SourcedUnitConfirmationBody(BaseModel):
    exact_expiry_date: date
    reason: str = Field(min_length=5, max_length=1000)


class NotificationTemplateBody(BaseModel):
    event_key: str = Field(min_length=1, max_length=100)
    channel: str = Field(pattern=r"^sms$")
    version: int = Field(ge=1)
    body_fa: str = Field(min_length=1, max_length=1000)
    activate: bool = False
    reason: str = Field(min_length=5, max_length=1000)


class OfferCapacityBody(BaseModel):
    status: str = Field(pattern=r"^(open|paused)$")
    max_pending_quantity: int | None = Field(default=None, gt=0)
    available_from: datetime | None = None
    available_until: datetime | None = None
    reason: str = Field(min_length=5, max_length=1000)


class PrivacyDecisionBody(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


class WebhookReplayBody(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


class BodyAssessmentConfirmationBody(BaseModel):
    veterinarian_name: str = Field(min_length=2, max_length=200)
    veterinarian_credential: str = Field(min_length=2, max_length=200)
    evidence_file_id: UUID
    reason: str = Field(min_length=5, max_length=2000)


class KnowledgeImportBody(BaseModel):
    bundle: dict[str, Any]
    reason: str = Field(min_length=5, max_length=2000)


class KnowledgeClaimReviewBody(BaseModel):
    decision: str = Field(pattern=r"^(approved|rejected)$")
    expected_claim_checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_file_id: UUID
    reviewed_at: datetime
    next_review_at: datetime | None = None
    credential_verified_privately: bool = False
    limitations_fa: str | None = Field(default=None, max_length=5000)
    reason: str = Field(min_length=5, max_length=2000)


class KnowledgePublishBody(BaseModel):
    expected_release_checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_file_id: UUID
    reviewed_at: datetime
    next_review_at: datetime | None = None
    credential_verified_privately: bool = False
    limitations_fa: str | None = Field(default=None, max_length=5000)
    supersedes_release_id: UUID | None = None
    reason: str = Field(min_length=5, max_length=2000)


class KnowledgeWithdrawBody(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


class KnowledgeBatchApprovalBody(BaseModel):
    expected_release_checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_file_id: UUID
    reviewed_at: datetime
    next_review_at: datetime | None = None
    credential_verified_privately: bool
    limitations_fa: str | None = Field(default=None, max_length=5000)
    reason: str = Field(min_length=5, max_length=2000)


class KnowledgeMaterializeBody(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


class KnowledgeGuidanceImportBody(BaseModel):
    guidance: list[dict[str, Any]]
    reason: str = Field(min_length=5, max_length=2000)


class KnowledgeActivationBody(BaseModel):
    release_id: UUID
    expected_release_checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_file_id: UUID
    reviewed_at: datetime
    next_review_at: datetime | None = None
    credential_verified_privately: bool
    limitations_fa: str | None = Field(default=None, max_length=5000)
    expected_guidance_count: int = Field(default=0, ge=0, le=100000)
    expected_benchmark_candidate_count: int = Field(default=0, ge=0, le=100000)
    reason: str = Field(min_length=5, max_length=2000)


class KnowledgeActivationActionBody(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


class BenchmarkDefinitionBody(BaseModel):
    expected_claim_checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    measurement_type: str = Field(pattern=r"^(weight|height_at_withers)$")
    unit: str = Field(pattern=r"^(kg|cm)$")
    reference_purpose: str = Field(
        pattern=r"^(registry_conformation|population_reference|growth_reference)$"
    )
    minimum_value: Decimal = Field(ge=0, max_digits=12, decimal_places=3)
    maximum_value: Decimal = Field(ge=0, max_digits=12, decimal_places=3)
    minimum_age_days: int | None = Field(default=None, ge=0, le=10000)
    maximum_age_days: int | None = Field(default=None, ge=0, le=10000)
    life_stage: str | None = Field(default=None, max_length=40)
    sex_scope: str = Field(pattern=r"^(combined|female|male)$")
    neuter_scope: str = Field(pattern=r"^(any|intact|neutered)$")
    population_geography: str = Field(min_length=2, max_length=200)
    measurement_definition_fa: str = Field(min_length=5, max_length=3000)
    comparison_allowed: bool = False
    reason: str = Field(min_length=5, max_length=2000)


@router.post("/knowledge-releases/validate", response_model=dict[str, object])
async def validate_knowledge_release(
    body: dict[str, Any], _: CurrentOperator
) -> dict[str, object]:
    result = validate_bundle(body)
    return {
        "valid": result.valid,
        "checksum_sha256": result.checksum_sha256,
        "counts": result.counts,
        "errors": list(result.errors),
        "warnings": list(result.warnings),
        "would_force_all_claims_non_public": True,
    }


@router.post(
    "/knowledge-releases/import",
    response_model=dict[str, object],
    status_code=status.HTTP_201_CREATED,
)
async def import_knowledge_release(
    body: KnowledgeImportBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> dict[str, object]:
    result = validate_bundle(body.bundle)
    if not result.valid:
        raise HTTPException(
            status_code=422,
            detail={"code": "knowledge_bundle_invalid", "errors": list(result.errors)},
        )
    existing = await session.scalar(
        select(KnowledgeRelease).where(
            or_(
                KnowledgeRelease.dataset_version == body.bundle["dataset_version"],
                KnowledgeRelease.checksum_sha256 == result.checksum_sha256,
            )
        )
    )
    if existing is not None:
        if existing.checksum_sha256 != result.checksum_sha256:
            raise HTTPException(status_code=409, detail="dataset_version_checksum_conflict")
        return {
            "id": existing.id,
            "status": existing.status,
            "checksum_sha256": existing.checksum_sha256,
            "idempotent_replay": True,
        }
    key = f"knowledge-releases/{result.checksum_sha256}.json"
    from app.main import get_storage

    await get_storage().put_bytes(key, canonical_bytes(body.bundle))
    release = await import_validated_bundle(
        session,
        bundle=body.bundle,
        validation=result,
        storage_key=key,
        operator_id=operator.id,
    )
    _audit(
        session,
        request,
        operator.id,
        "knowledge_release.imported",
        "knowledge_release",
        release.id,
        body.reason,
        {
            "dataset_version": release.dataset_version,
            "checksum_sha256": release.checksum_sha256,
            "counts": result.counts,
            "warnings": list(result.warnings),
            "claims_public": False,
        },
    )
    await session.commit()
    return {
        "id": release.id,
        "status": release.status,
        "checksum_sha256": release.checksum_sha256,
        "counts": result.counts,
        "warnings": list(result.warnings),
        "idempotent_replay": False,
    }


@router.post(
    "/knowledge-releases/{release_id}/guidance/import",
    response_model=dict[str, int],
    status_code=status.HTTP_201_CREATED,
)
async def import_knowledge_guidance(
    release_id: UUID,
    body: KnowledgeGuidanceImportBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> dict[str, int]:
    release = await session.get(KnowledgeRelease, release_id, with_for_update=True)
    if release is None:
        raise HTTPException(status_code=404, detail="knowledge_release_not_found")
    if release.status != "imported":
        raise HTTPException(status_code=409, detail="knowledge_release_not_importable")
    claim_ids = set(
        (
            await session.scalars(
                select(KnowledgeClaim.external_id).where(
                    KnowledgeClaim.release_id == release.id
                )
            )
        ).all()
    )
    breeds = set(
        (
            await session.scalars(
                select(KnowledgeBreed.external_id).where(KnowledgeBreed.release_id == release.id)
            )
        ).all()
    )
    varieties = {
        item.external_id: item.breed_external_id
        for item in (
            await session.scalars(
                select(KnowledgeVariety).where(KnowledgeVariety.release_id == release.id)
            )
        ).all()
    }
    existing_count = int(
        await session.scalar(
            select(func.count(KnowledgeGuidance.id)).where(
                KnowledgeGuidance.release_id == release.id
            )
        )
        or 0
    )
    if existing_count:
        if existing_count == len(body.guidance):
            return {"imported": 0, "total": existing_count}
        raise HTTPException(status_code=409, detail="guidance_import_conflict")
    seen: set[str] = set()
    for index, record in enumerate(body.guidance):
        guidance_id = record.get("guidance_id")
        target = record.get("breed_or_variety_id")
        text_fa = record.get("guidance_fa")
        supporting = record.get("supporting_claim_ids")
        if not isinstance(guidance_id, str) or not guidance_id or guidance_id in seen:
            raise HTTPException(status_code=422, detail=f"invalid_guidance_id:{index}")
        if not isinstance(text_fa, str) or not text_fa.strip():
            raise HTTPException(status_code=422, detail=f"invalid_guidance_text:{guidance_id}")
        if not isinstance(supporting, list) or not supporting or not set(supporting) <= claim_ids:
            raise HTTPException(status_code=422, detail=f"invalid_guidance_claims:{guidance_id}")
        variety_id = target if target in varieties else None
        breed_id = varieties.get(str(target), str(target))
        if breed_id not in breeds:
            raise HTTPException(status_code=422, detail=f"invalid_guidance_target:{guidance_id}")
        seen.add(guidance_id)
        session.add(
            KnowledgeGuidance(
                release_id=release.id,
                external_id=guidance_id,
                breed_external_id=breed_id,
                variety_external_id=variety_id,
                domain=str(record.get("domain") or "care"),
                text_fa=text_fa,
                supporting_claim_external_ids=supporting,
                review_status="veterinary_review_required",
                app_eligible=False,
                record={**record, "app_eligible": False},
            )
        )
    _audit(
        session,
        request,
        operator.id,
        "knowledge_guidance.imported",
        "knowledge_release",
        release.id,
        body.reason,
        {"imported": len(body.guidance), "forced_non_public": True},
    )
    await session.commit()
    return {"imported": len(body.guidance), "total": len(body.guidance)}


@router.get("/knowledge-releases", response_model=list[dict[str, object]])
async def list_knowledge_releases(
    _: CurrentOperator, session: SessionDependency
) -> list[dict[str, object]]:
    releases = list(
        (
            await session.scalars(
                select(KnowledgeRelease).order_by(KnowledgeRelease.imported_at.desc()).limit(100)
            )
        ).all()
    )
    return [
        {
            "id": item.id,
            "schema_version": item.schema_version,
            "dataset_version": item.dataset_version,
            "language": item.language,
            "status": item.status,
            "checksum_sha256": item.checksum_sha256,
            "imported_at": item.imported_at,
            "counts": {
                "breeds": item.breed_count,
                "varieties": item.variety_count,
                "sources": item.source_count,
                "claims": item.claim_count,
            },
        }
        for item in releases
    ]


@router.post(
    "/knowledge-releases/{release_id}/batch-approve",
    response_model=dict[str, object],
)
async def batch_approve_knowledge_release(
    release_id: UUID,
    body: KnowledgeBatchApprovalBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> dict[str, object]:
    release = await session.get(KnowledgeRelease, release_id, with_for_update=True)
    if release is None:
        raise HTTPException(status_code=404, detail="knowledge_release_not_found")
    if release.status != "imported":
        raise HTTPException(status_code=409, detail="knowledge_release_not_reviewable")
    if release.checksum_sha256 != body.expected_release_checksum_sha256:
        raise HTTPException(status_code=409, detail="knowledge_release_checksum_mismatch")
    if not body.credential_verified_privately:
        raise HTTPException(status_code=422, detail="certified_reviewer_verification_required")
    evidence = await session.get(EvidenceFile, body.evidence_file_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="knowledge_review_evidence_not_found")
    if body.reviewed_at > utc_now():
        raise HTTPException(status_code=422, detail="review_cannot_be_in_future")
    if body.next_review_at is not None and body.next_review_at <= body.reviewed_at:
        raise HTTPException(status_code=422, detail="next_review_must_follow_review")
    claims = list(
        (
            await session.scalars(
                select(KnowledgeClaim)
                .where(KnowledgeClaim.release_id == release.id)
                .order_by(KnowledgeClaim.external_id)
                .with_for_update()
            )
        ).all()
    )
    approved = 0
    for claim in claims:
        already = await session.scalar(
            select(KnowledgeReview.id).where(
                KnowledgeReview.claim_id == claim.id,
                KnowledgeReview.decision == "approved",
                KnowledgeReview.reviewed_checksum_sha256
                == hashlib.sha256(canonical_bytes(claim.record)).hexdigest(),
            )
        )
        if already is not None:
            claim.review_status = "veterinary_approved"
            claim.app_eligible = True
            continue
        claim_checksum = hashlib.sha256(canonical_bytes(claim.record)).hexdigest()
        claim.review_status = "veterinary_approved"
        claim.app_eligible = True
        session.add(
            KnowledgeReview(
                release_id=release.id,
                claim_id=claim.id,
                scope="claim",
                decision="approved",
                reviewer_disclosure="anonymous_external_veterinarian",
                reviewed_checksum_sha256=claim_checksum,
                evidence_file_id=evidence.id,
                recorded_by_operator_id=operator.id,
                reviewed_at=body.reviewed_at,
                next_review_at=body.next_review_at,
                limitations_fa=body.limitations_fa,
                credential_verified_privately=True,
            )
        )
        approved += 1
    guidance_rows = list(
        (
            await session.scalars(
                select(KnowledgeGuidance)
                .where(KnowledgeGuidance.release_id == release.id)
                .order_by(KnowledgeGuidance.external_id)
                .with_for_update()
            )
        ).all()
    )
    guidance_approved = 0
    for guidance in guidance_rows:
        guidance_checksum = hashlib.sha256(canonical_bytes(guidance.record)).hexdigest()
        guidance.review_status = "veterinary_approved"
        guidance.app_eligible = True
        session.add(
            KnowledgeReview(
                release_id=release.id,
                claim_id=None,
                guidance_id=guidance.id,
                scope="guidance",
                decision="approved",
                reviewer_disclosure="anonymous_external_veterinarian",
                reviewed_checksum_sha256=guidance_checksum,
                evidence_file_id=evidence.id,
                recorded_by_operator_id=operator.id,
                reviewed_at=body.reviewed_at,
                next_review_at=body.next_review_at,
                limitations_fa=body.limitations_fa,
                credential_verified_privately=True,
            )
        )
        guidance_approved += 1
    _audit(
        session,
        request,
        operator.id,
        "knowledge_release.claims_batch_approved",
        "knowledge_release",
        release.id,
        body.reason,
        {
            "approved_claim_count": approved,
            "total_claim_count": len(claims),
            "approved_guidance_count": guidance_approved,
            "credential_verified_privately": True,
            "reviewer_disclosure": "anonymous_external_veterinarian",
            "evidence_file_id": str(evidence.id),
        },
    )
    await session.commit()
    return {
        "release_id": release.id,
        "approved_claims": approved,
        "total_claims": len(claims),
        "approved_guidance": guidance_approved,
        "total_guidance": len(guidance_rows),
        "reviewer_disclosure": "anonymous_external_veterinarian",
        "credential_verified_privately": True,
    }


@router.get(
    "/knowledge-releases/{release_id}/reconciliation",
    response_model=dict[str, object],
)
async def knowledge_release_reconciliation(
    release_id: UUID, _: CurrentOperator, session: SessionDependency
) -> dict[str, object]:
    release = await session.get(KnowledgeRelease, release_id)
    if release is None:
        raise HTTPException(status_code=404, detail="knowledge_release_not_found")
    claim_rows = (
        await session.execute(
            select(KnowledgeClaim.review_status, func.count(KnowledgeClaim.id))
            .where(KnowledgeClaim.release_id == release.id)
            .group_by(KnowledgeClaim.review_status)
        )
    ).all()
    benchmark_count = int(
        await session.scalar(
            select(func.count(BenchmarkDefinition.id)).where(
                BenchmarkDefinition.release_id == release.id
            )
        )
        or 0
    )
    guidance_rows = (
        await session.execute(
            select(KnowledgeGuidance.review_status, func.count(KnowledgeGuidance.id))
            .where(KnowledgeGuidance.release_id == release.id)
            .group_by(KnowledgeGuidance.review_status)
        )
    ).all()
    return {
        "release_id": release.id,
        "dataset_version": release.dataset_version,
        "status": release.status,
        "checksum_sha256": release.checksum_sha256,
        "stored_counts": {
            "breeds": release.breed_count,
            "varieties": release.variety_count,
            "sources": release.source_count,
            "claims": release.claim_count,
        },
        "claim_status_counts": {status_: count for status_, count in claim_rows},
        "guidance_status_counts": {status_: count for status_, count in guidance_rows},
        "benchmark_definitions": benchmark_count,
    }


@router.post(
    "/knowledge-activation-runs",
    response_model=dict[str, object],
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_activation_run(
    body: KnowledgeActivationBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> dict[str, object]:
    if not body.credential_verified_privately:
        raise HTTPException(status_code=422, detail="certified_reviewer_verification_required")
    release = await session.get(KnowledgeRelease, body.release_id, with_for_update=True)
    if release is None:
        raise HTTPException(status_code=404, detail="knowledge_release_not_found")
    evidence = await session.get(EvidenceFile, body.evidence_file_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="knowledge_review_evidence_not_found")
    existing = await session.scalar(
        select(KnowledgeActivationRun).where(KnowledgeActivationRun.release_id == release.id)
    )
    if existing is not None:
        return _activation_item(existing)
    preflight = await build_activation_preflight(
        session,
        release=release,
        expected_checksum=body.expected_release_checksum_sha256,
        reviewed_at=body.reviewed_at,
        next_review_at=body.next_review_at,
        expected_guidance_count=body.expected_guidance_count,
        expected_benchmark_candidate_count=body.expected_benchmark_candidate_count,
    )
    previous_id = preflight.get("previous_release_id")
    run = KnowledgeActivationRun(
        release_id=release.id,
        previous_release_id=UUID(previous_id) if isinstance(previous_id, str) else None,
        evidence_file_id=evidence.id,
        expected_release_checksum_sha256=body.expected_release_checksum_sha256,
        expected_guidance_count=body.expected_guidance_count,
        expected_benchmark_candidate_count=body.expected_benchmark_candidate_count,
        reviewed_at=body.reviewed_at,
        next_review_at=body.next_review_at,
        limitations_fa=body.limitations_fa,
        status="ready" if preflight["ready"] else "blocked",
        preflight_report=preflight,
        created_by_operator_id=operator.id,
    )
    session.add(run)
    await session.flush()
    _audit(
        session,
        request,
        operator.id,
        "knowledge_activation.preflight_created",
        "knowledge_activation_run",
        run.id,
        body.reason,
        {"status": run.status, "preflight": preflight},
    )
    await session.commit()
    return _activation_item(run)


@router.get("/knowledge-activation-runs/{run_id}", response_model=dict[str, object])
async def get_knowledge_activation_run(
    run_id: UUID, _: CurrentOperator, session: SessionDependency
) -> dict[str, object]:
    run = await session.get(KnowledgeActivationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="knowledge_activation_not_found")
    return _activation_item(run)


@router.post(
    "/knowledge-activation-runs/{run_id}/preflight", response_model=dict[str, object]
)
async def refresh_knowledge_activation_preflight(
    run_id: UUID,
    body: KnowledgeActivationActionBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> dict[str, object]:
    run = await session.get(KnowledgeActivationRun, run_id, with_for_update=True)
    if run is None:
        raise HTTPException(status_code=404, detail="knowledge_activation_not_found")
    if run.status not in {"blocked", "ready", "failed"}:
        raise HTTPException(status_code=409, detail="knowledge_activation_preflight_locked")
    release = await session.get(KnowledgeRelease, run.release_id)
    if release is None:
        raise HTTPException(status_code=404, detail="knowledge_release_not_found")
    preflight = await build_activation_preflight(
        session,
        release=release,
        expected_checksum=run.expected_release_checksum_sha256,
        reviewed_at=run.reviewed_at,
        next_review_at=run.next_review_at,
        expected_guidance_count=run.expected_guidance_count,
        expected_benchmark_candidate_count=run.expected_benchmark_candidate_count,
    )
    run.preflight_report = preflight
    run.status = "ready" if preflight["ready"] else "blocked"
    run.failure_code = None
    _audit(
        session,
        request,
        operator.id,
        "knowledge_activation.preflight_refreshed",
        "knowledge_activation_run",
        run.id,
        body.reason,
        {"status": run.status, "preflight": preflight},
    )
    await session.commit()
    return _activation_item(run)


@router.post(
    "/knowledge-activation-runs/{run_id}/execute", response_model=dict[str, object]
)
async def execute_knowledge_activation_run(
    run_id: UUID,
    body: KnowledgeActivationActionBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> dict[str, object]:
    run = await session.get(KnowledgeActivationRun, run_id, with_for_update=True)
    if run is None:
        raise HTTPException(status_code=404, detail="knowledge_activation_not_found")
    if run.status == "completed":
        return _activation_item(run)
    if run.status != "ready":
        raise HTTPException(status_code=409, detail="knowledge_activation_not_ready")
    try:
        result = await execute_activation(session, run=run, operator_id=operator.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(
        session,
        request,
        operator.id,
        "knowledge_activation.completed",
        "knowledge_activation_run",
        run.id,
        body.reason,
        result,
    )
    await session.commit()
    return _activation_item(run)


@router.post(
    "/knowledge-activation-runs/{run_id}/rollback", response_model=dict[str, object]
)
async def rollback_knowledge_activation_run(
    run_id: UUID,
    body: KnowledgeActivationActionBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> dict[str, object]:
    run = await session.get(KnowledgeActivationRun, run_id, with_for_update=True)
    if run is None:
        raise HTTPException(status_code=404, detail="knowledge_activation_not_found")
    if run.status == "rolled_back":
        return _activation_item(run)
    try:
        result = await rollback_activation(session, run=run)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(
        session,
        request,
        operator.id,
        "knowledge_activation.rolled_back",
        "knowledge_activation_run",
        run.id,
        body.reason,
        result,
    )
    await session.commit()
    return _activation_item(run)


@router.post("/knowledge-claims/{claim_id}/review", status_code=status.HTTP_204_NO_CONTENT)
async def record_knowledge_claim_review(
    claim_id: UUID,
    body: KnowledgeClaimReviewBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> None:
    claim = await session.get(KnowledgeClaim, claim_id, with_for_update=True)
    if claim is None:
        raise HTTPException(status_code=404, detail="knowledge_claim_not_found")
    release = await session.get(KnowledgeRelease, claim.release_id)
    if release is None or release.status != "imported":
        raise HTTPException(status_code=409, detail="knowledge_release_not_reviewable")
    claim_checksum = hashlib.sha256(canonical_bytes(claim.record)).hexdigest()
    if claim_checksum != body.expected_claim_checksum_sha256:
        raise HTTPException(status_code=409, detail="knowledge_claim_checksum_mismatch")
    evidence = await session.get(EvidenceFile, body.evidence_file_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="knowledge_review_evidence_not_found")
    if body.reviewed_at > utc_now():
        raise HTTPException(status_code=422, detail="review_cannot_be_in_future")
    if body.next_review_at is not None and body.next_review_at <= body.reviewed_at:
        raise HTTPException(status_code=422, detail="next_review_must_follow_review")
    if not body.credential_verified_privately:
        raise HTTPException(status_code=422, detail="certified_reviewer_verification_required")
    claim.review_status = (
        "veterinary_approved" if body.decision == "approved" else "rejected"
    )
    claim.app_eligible = body.decision == "approved"
    session.add(
        KnowledgeReview(
            release_id=release.id,
            claim_id=claim.id,
            scope="claim",
            decision=body.decision,
            reviewer_disclosure="anonymous_external_veterinarian",
            reviewed_checksum_sha256=claim_checksum,
            evidence_file_id=evidence.id,
            recorded_by_operator_id=operator.id,
            reviewed_at=body.reviewed_at,
            next_review_at=body.next_review_at,
            limitations_fa=body.limitations_fa,
            credential_verified_privately=True,
        )
    )
    _audit(
        session,
        request,
        operator.id,
        f"knowledge_claim.{body.decision}",
        "knowledge_claim",
        claim.id,
        body.reason,
        {
            "reviewer_disclosure": "anonymous_external_veterinarian",
            "reviewed_checksum_sha256": claim_checksum,
            "evidence_file_id": str(evidence.id),
            "app_eligible": claim.app_eligible,
        },
    )
    await session.commit()


@router.get("/knowledge-review-tasks", response_model=list[dict[str, object]])
async def list_knowledge_review_tasks(
    _: CurrentOperator,
    session: SessionDependency,
    task_status: Annotated[str | None, Query(pattern=r"^(due|expired|resolved)$")] = None,
) -> list[dict[str, object]]:
    query = (
        select(KnowledgeReviewTask, KnowledgeReview)
        .join(KnowledgeReview, KnowledgeReview.id == KnowledgeReviewTask.review_id)
        .order_by(KnowledgeReviewTask.due_at)
    )
    if task_status is not None:
        query = query.where(KnowledgeReviewTask.status == task_status)
    rows = (await session.execute(query.limit(200))).all()
    return [
        {
            "id": task.id,
            "status": task.status,
            "due_at": task.due_at,
            "scope": review.scope,
            "release_id": review.release_id,
            "claim_id": review.claim_id,
            "reviewer_disclosure": review.reviewer_disclosure,
            "reviewed_checksum_sha256": review.reviewed_checksum_sha256,
            "limitations_fa": review.limitations_fa,
        }
        for task, review in rows
    ]


@router.post(
    "/knowledge-claims/{claim_id}/benchmark",
    response_model=dict[str, object],
    status_code=status.HTTP_201_CREATED,
)
async def create_benchmark_definition(
    claim_id: UUID,
    body: BenchmarkDefinitionBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> dict[str, object]:
    claim = await session.get(KnowledgeClaim, claim_id, with_for_update=True)
    if claim is None:
        raise HTTPException(status_code=404, detail="knowledge_claim_not_found")
    release = await session.get(KnowledgeRelease, claim.release_id)
    if (
        release is None
        or release.status != "published"
        or claim.review_status != "veterinary_approved"
        or not claim.app_eligible
    ):
        raise HTTPException(status_code=409, detail="approved_published_claim_required")
    checksum = hashlib.sha256(canonical_bytes(claim.record)).hexdigest()
    if checksum != body.expected_claim_checksum_sha256:
        raise HTTPException(status_code=409, detail="knowledge_claim_checksum_mismatch")
    expected_claim_type = {
        "weight": "adult_weight_reference",
        "height_at_withers": "height_reference",
    }[body.measurement_type]
    if claim.claim_type != expected_claim_type:
        raise HTTPException(status_code=422, detail="claim_type_measurement_mismatch")
    expected_unit = {"weight": "kg", "height_at_withers": "cm"}[body.measurement_type]
    if body.unit != expected_unit:
        raise HTTPException(status_code=422, detail="benchmark_unit_measurement_mismatch")
    if body.maximum_value < body.minimum_value:
        raise HTTPException(status_code=422, detail="benchmark_range_reversed")
    if (
        body.minimum_age_days is not None
        and body.maximum_age_days is not None
        and body.maximum_age_days < body.minimum_age_days
    ):
        raise HTTPException(status_code=422, detail="benchmark_age_range_reversed")
    if body.reference_purpose == "registry_conformation" and body.comparison_allowed:
        raise HTTPException(status_code=422, detail="registry_range_cannot_classify_pet")
    existing = await session.scalar(
        select(BenchmarkDefinition).where(BenchmarkDefinition.claim_id == claim.id)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="benchmark_definition_exists")
    benchmark = BenchmarkDefinition(
        release_id=release.id,
        claim_id=claim.id,
        breed_external_id=claim.breed_external_id,
        variety_external_id=claim.variety_external_id,
        measurement_type=body.measurement_type,
        unit=body.unit,
        reference_purpose=body.reference_purpose,
        minimum_value=body.minimum_value,
        maximum_value=body.maximum_value,
        minimum_age_days=body.minimum_age_days,
        maximum_age_days=body.maximum_age_days,
        life_stage=body.life_stage,
        sex_scope=body.sex_scope,
        neuter_scope=body.neuter_scope,
        population_geography=body.population_geography,
        measurement_definition_fa=body.measurement_definition_fa,
        comparison_allowed=body.comparison_allowed,
        status="active",
        recorded_by_operator_id=operator.id,
    )
    session.add(benchmark)
    _audit(
        session,
        request,
        operator.id,
        "knowledge_benchmark.created",
        "knowledge_claim",
        claim.id,
        body.reason,
        {
            "benchmark_id": str(benchmark.id),
            "reviewed_checksum_sha256": checksum,
            "reference_purpose": body.reference_purpose,
            "comparison_allowed": body.comparison_allowed,
        },
    )
    await session.commit()
    return {"id": benchmark.id, "status": benchmark.status}


@router.post(
    "/knowledge-releases/{release_id}/publish",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def publish_knowledge_release(
    release_id: UUID,
    body: KnowledgePublishBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> None:
    release = await session.get(KnowledgeRelease, release_id, with_for_update=True)
    if release is None:
        raise HTTPException(status_code=404, detail="knowledge_release_not_found")
    if release.status != "imported":
        raise HTTPException(status_code=409, detail="knowledge_release_not_publishable")
    if release.checksum_sha256 != body.expected_release_checksum_sha256:
        raise HTTPException(status_code=409, detail="knowledge_release_checksum_mismatch")
    evidence = await session.get(EvidenceFile, body.evidence_file_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="knowledge_review_evidence_not_found")
    if body.reviewed_at > utc_now():
        raise HTTPException(status_code=422, detail="review_cannot_be_in_future")
    if body.next_review_at is not None and body.next_review_at <= body.reviewed_at:
        raise HTTPException(status_code=422, detail="next_review_must_follow_review")
    if not body.credential_verified_privately:
        raise HTTPException(status_code=422, detail="certified_reviewer_verification_required")
    approved_count = int(
        await session.scalar(
            select(func.count(KnowledgeClaim.id)).where(
                KnowledgeClaim.release_id == release.id,
                KnowledgeClaim.review_status == "veterinary_approved",
                KnowledgeClaim.app_eligible.is_(True),
            )
        )
        or 0
    )
    if approved_count == 0:
        raise HTTPException(status_code=409, detail="approved_claim_required_for_publication")
    current = await session.scalar(
        select(KnowledgeRelease)
        .where(KnowledgeRelease.status == "published")
        .with_for_update()
    )
    if current is not None:
        if body.supersedes_release_id != current.id:
            raise HTTPException(status_code=409, detail="published_release_must_be_superseded")
        current.status = "superseded"
    elif body.supersedes_release_id is not None:
        raise HTTPException(status_code=409, detail="superseded_release_not_current")
    now = utc_now()
    release.status = "published"
    release.published_at = now
    release.supersedes_release_id = body.supersedes_release_id
    session.add(
        KnowledgeReview(
            release_id=release.id,
            claim_id=None,
            scope="release",
            decision="approved",
            reviewer_disclosure="anonymous_external_veterinarian",
            reviewed_checksum_sha256=release.checksum_sha256,
            evidence_file_id=evidence.id,
            recorded_by_operator_id=operator.id,
            reviewed_at=body.reviewed_at,
            next_review_at=body.next_review_at,
            limitations_fa=body.limitations_fa,
            credential_verified_privately=True,
        )
    )
    _audit(
        session,
        request,
        operator.id,
        "knowledge_release.published",
        "knowledge_release",
        release.id,
        body.reason,
        {
            "checksum_sha256": release.checksum_sha256,
            "approved_claim_count": approved_count,
            "reviewer_disclosure": "anonymous_external_veterinarian",
            "supersedes_release_id": (
                str(body.supersedes_release_id) if body.supersedes_release_id else None
            ),
        },
    )
    await session.commit()


@router.post(
    "/knowledge-releases/{release_id}/materialize-benchmarks",
    response_model=dict[str, int],
)
async def materialize_knowledge_benchmarks(
    release_id: UUID,
    body: KnowledgeMaterializeBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> dict[str, int]:
    release = await session.get(KnowledgeRelease, release_id, with_for_update=True)
    if release is None:
        raise HTTPException(status_code=404, detail="knowledge_release_not_found")
    if release.status != "published":
        raise HTTPException(status_code=409, detail="published_release_required")
    result = await materialize_release_benchmarks(
        session, release=release, operator_id=operator.id
    )
    audit_metadata: dict[str, object] = dict(result)
    _audit(
        session,
        request,
        operator.id,
        "knowledge_release.benchmarks_materialized",
        "knowledge_release",
        release.id,
        body.reason,
        audit_metadata,
    )
    await session.commit()
    return result


@router.post(
    "/knowledge-claims/{claim_id}/withdraw",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def withdraw_knowledge_claim(
    claim_id: UUID,
    body: KnowledgeWithdrawBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> None:
    claim = await session.get(KnowledgeClaim, claim_id, with_for_update=True)
    if claim is None:
        raise HTTPException(status_code=404, detail="knowledge_claim_not_found")
    claim.review_status = "withdrawn"
    claim.app_eligible = False
    _audit(
        session,
        request,
        operator.id,
        "knowledge_claim.withdrawn",
        "knowledge_claim",
        claim.id,
        body.reason,
        {"app_eligible": False},
    )
    await session.commit()


@router.post(
    "/knowledge-releases/{release_id}/withdraw",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def withdraw_knowledge_release(
    release_id: UUID,
    body: KnowledgeWithdrawBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> None:
    release = await session.get(KnowledgeRelease, release_id, with_for_update=True)
    if release is None:
        raise HTTPException(status_code=404, detail="knowledge_release_not_found")
    if release.status not in {"imported", "published"}:
        raise HTTPException(status_code=409, detail="knowledge_release_not_withdrawable")
    release.status = "withdrawn"
    release.withdrawn_at = utc_now()
    claims = list(
        (
            await session.scalars(
                select(KnowledgeClaim).where(KnowledgeClaim.release_id == release.id)
            )
        ).all()
    )
    for claim in claims:
        claim.app_eligible = False
        if claim.review_status == "veterinary_approved":
            claim.review_status = "withdrawn"
    _audit(
        session,
        request,
        operator.id,
        "knowledge_release.withdrawn",
        "knowledge_release",
        release.id,
        body.reason,
        {"claims_disabled": len(claims)},
    )
    await session.commit()


@router.post("/suppliers", response_model=CreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    body: SupplierBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> CreatedResponse:
    supplier = Supplier(
        internal_name=body.internal_name,
        country_code=body.country_code,
        active=True,
    )
    session.add(supplier)
    await session.flush()
    _audit(
        session,
        request,
        operator.id,
        "supplier.created",
        "supplier",
        supplier.id,
        body.reason,
        {
            "country_code": supplier.country_code,
            "active": supplier.active,
        },
    )
    await session.commit()
    return CreatedResponse(id=supplier.id)


@router.post("/products", response_model=CreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> CreatedResponse:
    product = Product(name_fa=body.name_fa, description_fa=body.description_fa, status="active")
    session.add(product)
    await session.flush()
    _audit(
        session,
        request,
        operator.id,
        "product.created",
        "product",
        product.id,
        body.reason,
        {
            "name_fa": product.name_fa,
            "status": product.status,
        },
    )
    await session.commit()
    return CreatedResponse(id=product.id)


@router.post("/offers", response_model=CreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(
    body: OfferBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> CreatedResponse:
    if (
        body.available_from is not None
        and body.available_until is not None
        and body.available_until <= body.available_from
    ):
        raise HTTPException(status_code=422, detail="invalid_availability_window")
    if (
        await session.get(Product, body.product_id) is None
        or await session.get(Supplier, body.supplier_id) is None
    ):
        raise HTTPException(status_code=404, detail="product_or_supplier_not_found")
    assurance = await session.scalar(
        select(SupplierAssurance).where(
            SupplierAssurance.supplier_id == body.supplier_id,
            SupplierAssurance.active.is_(True),
        )
    )
    if assurance is None:
        raise HTTPException(status_code=409, detail="active_supplier_assurance_required")
    offer = Offer(
        product_id=body.product_id,
        supplier_id=body.supplier_id,
        sku=body.sku,
        title_fa=body.title_fa,
        unit_label_fa=body.unit_label_fa,
        price_irr=body.price_irr,
        reference_price_irr=None,
        reference_price_reviewed_at=None,
        status="active",
        stock_posture="sourced_after_payment",
        minimum_shelf_life_months=body.minimum_shelf_life_months,
        available_from=body.available_from,
        available_until=body.available_until,
        max_pending_quantity=body.max_pending_quantity,
        sourcing_capacity_status="open",
    )
    session.add(offer)
    await session.flush()
    _audit(
        session,
        request,
        operator.id,
        "offer.created",
        "offer",
        offer.id,
        body.reason,
        {
            "sku": offer.sku,
            "price_irr": offer.price_irr,
            "stock_posture": offer.stock_posture,
        },
    )
    await session.commit()
    return CreatedResponse(id=offer.id)


@router.put("/offers/{offer_id}/capacity", status_code=status.HTTP_204_NO_CONTENT)
async def update_offer_capacity(
    offer_id: UUID,
    body: OfferCapacityBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> None:
    offer = await session.get(Offer, offer_id, with_for_update=True)
    if offer is None:
        raise HTTPException(status_code=404, detail="offer_not_found")
    if (
        body.available_from is not None
        and body.available_until is not None
        and body.available_until <= body.available_from
    ):
        raise HTTPException(status_code=422, detail="invalid_availability_window")
    before = {
        "status": offer.sourcing_capacity_status,
        "max_pending_quantity": offer.max_pending_quantity,
    }
    offer.sourcing_capacity_status = body.status
    offer.max_pending_quantity = body.max_pending_quantity
    offer.available_from = body.available_from
    offer.available_until = body.available_until
    _audit(
        session,
        request,
        operator.id,
        "offer.capacity_updated",
        "offer",
        offer.id,
        body.reason,
        {
            "before": before,
            "status": offer.sourcing_capacity_status,
            "max_pending_quantity": offer.max_pending_quantity,
        },
    )
    await notify_available_subscribers(session, offer)
    await session.commit()


class OfferSourcingConfigBody(BaseModel):
    sourcing_route: str = Field(pattern=r"^(aggregated|individual)$")
    default_batch_threshold_quantity: int | None = Field(default=None, gt=0)
    reason: str = Field(min_length=5, max_length=1000)


@router.patch("/offers/{offer_id}/sourcing-config", status_code=status.HTTP_204_NO_CONTENT)
async def update_offer_sourcing_config(
    offer_id: UUID,
    body: OfferSourcingConfigBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> None:
    offer = await session.get(Offer, offer_id, with_for_update=True)
    if offer is None:
        raise HTTPException(status_code=404, detail="offer_not_found")
    before = {
        "sourcing_route": offer.sourcing_route,
        "default_batch_threshold_quantity": offer.default_batch_threshold_quantity,
    }
    offer.sourcing_route = body.sourcing_route
    offer.default_batch_threshold_quantity = body.default_batch_threshold_quantity
    _audit(
        session,
        request,
        operator.id,
        "offer.sourcing_config_updated",
        "offer",
        offer.id,
        body.reason,
        {
            "before": before,
            "sourcing_route": offer.sourcing_route,
            "default_batch_threshold_quantity": offer.default_batch_threshold_quantity,
        },
    )
    await session.commit()


class PurchaseBatchResponse(BaseModel):
    id: UUID
    offer_id: UUID
    grouping_mode: str
    status: str
    deadline_at: datetime | None
    minimum_viable_threshold_quantity: int
    allocated_quantity: int
    threshold_reached_at: datetime | None
    committed_at: datetime | None
    committed_by_operator_id: UUID | None
    commitment_evidence_file_id: UUID | None
    commitment_reference: str | None
    cancelled_at: datetime | None
    cancelled_by_operator_id: UUID | None
    created_at: datetime


class PurchaseBatchAllocationResponse(BaseModel):
    id: UUID
    order_line_id: UUID
    quantity: int
    allocated_at: datetime


class PurchaseBatchEventResponse(BaseModel):
    id: UUID
    event_type: str
    occurred_at: datetime
    reason: str | None
    operator_identity_id: UUID | None


class PurchaseBatchDetailResponse(PurchaseBatchResponse):
    allocations: list[PurchaseBatchAllocationResponse]
    events: list[PurchaseBatchEventResponse]


class PurchaseBatchAdjustBody(BaseModel):
    minimum_viable_threshold_quantity: int = Field(gt=0)
    deadline_at: datetime | None = None
    reason: str = Field(min_length=5, max_length=1000)


class PurchaseBatchCommitBody(BaseModel):
    evidence_file_id: UUID
    commitment_reference: str | None = Field(default=None, max_length=300)
    reason: str = Field(min_length=5, max_length=1000)


def _purchase_batch_response(batch: PurchaseBatch) -> PurchaseBatchResponse:
    return PurchaseBatchResponse(
        id=batch.id,
        offer_id=batch.offer_id,
        grouping_mode=batch.grouping_mode,
        status=batch.status,
        deadline_at=batch.deadline_at,
        minimum_viable_threshold_quantity=batch.minimum_viable_threshold_quantity,
        allocated_quantity=batch.allocated_quantity,
        threshold_reached_at=batch.threshold_reached_at,
        committed_at=batch.committed_at,
        committed_by_operator_id=batch.committed_by_operator_id,
        commitment_evidence_file_id=batch.commitment_evidence_file_id,
        commitment_reference=batch.commitment_reference,
        cancelled_at=batch.cancelled_at,
        cancelled_by_operator_id=batch.cancelled_by_operator_id,
        created_at=batch.created_at,
    )


@router.get("/purchase-batches", response_model=list[PurchaseBatchResponse])
async def list_purchase_batches(
    _: CurrentOperator,
    session: SessionDependency,
    offer_id: UUID | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[PurchaseBatchResponse]:
    if status_filter is not None and status_filter not in ("open", "committed", "cancelled"):
        raise HTTPException(status_code=422, detail="invalid_status_filter")
    query = select(PurchaseBatch).order_by(PurchaseBatch.created_at.desc())
    if offer_id is not None:
        query = query.where(PurchaseBatch.offer_id == offer_id)
    if status_filter is not None:
        query = query.where(PurchaseBatch.status == status_filter)
    rows = list((await session.scalars(query.limit(200))).all())
    return [_purchase_batch_response(row) for row in rows]


@router.get("/purchase-batches/{batch_id}", response_model=PurchaseBatchDetailResponse)
async def get_purchase_batch(
    batch_id: UUID, _: CurrentOperator, session: SessionDependency
) -> PurchaseBatchDetailResponse:
    batch = await session.get(PurchaseBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="purchase_batch_not_found")
    allocations = list(
        (
            await session.scalars(
                select(PurchaseBatchAllocation)
                .where(PurchaseBatchAllocation.purchase_batch_id == batch.id)
                .order_by(PurchaseBatchAllocation.allocated_at)
            )
        ).all()
    )
    events = list(
        (
            await session.scalars(
                select(PurchaseBatchEvent)
                .where(PurchaseBatchEvent.purchase_batch_id == batch.id)
                .order_by(PurchaseBatchEvent.occurred_at)
            )
        ).all()
    )
    return PurchaseBatchDetailResponse(
        **_purchase_batch_response(batch).model_dump(),
        allocations=[
            PurchaseBatchAllocationResponse(
                id=item.id,
                order_line_id=item.order_line_id,
                quantity=item.quantity,
                allocated_at=item.allocated_at,
            )
            for item in allocations
        ],
        events=[
            PurchaseBatchEventResponse(
                id=item.id,
                event_type=item.event_type,
                occurred_at=item.occurred_at,
                reason=item.reason,
                operator_identity_id=item.operator_identity_id,
            )
            for item in events
        ],
    )


@router.patch("/purchase-batches/{batch_id}", response_model=PurchaseBatchResponse)
async def adjust_purchase_batch(
    batch_id: UUID,
    body: PurchaseBatchAdjustBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> PurchaseBatchResponse:
    batch = await session.get(PurchaseBatch, batch_id, with_for_update=True)
    if batch is None:
        raise HTTPException(status_code=404, detail="purchase_batch_not_found")
    if batch.status != "open":
        raise HTTPException(status_code=409, detail="purchase_batch_not_open")
    before = {
        "minimum_viable_threshold_quantity": batch.minimum_viable_threshold_quantity,
        "deadline_at": batch.deadline_at.isoformat() if batch.deadline_at else None,
    }
    batch.minimum_viable_threshold_quantity = body.minimum_viable_threshold_quantity
    batch.deadline_at = body.deadline_at
    # A lowered threshold can retroactively cross what's already allocated.
    # threshold_reached_at is a forward-only, system-computed fact (ADR-006)
    # -- once set it is never unset by a later, higher threshold.
    newly_reached = False
    if (
        batch.threshold_reached_at is None
        and batch.allocated_quantity >= batch.minimum_viable_threshold_quantity
    ):
        batch.threshold_reached_at = utc_now()
        newly_reached = True
        session.add(
            PurchaseBatchEvent(
                purchase_batch_id=batch.id,
                event_type="threshold_reached",
                occurred_at=batch.threshold_reached_at,
                reason=body.reason,
                operator_identity_id=operator.id,
            )
        )
    await session.flush()
    _audit(
        session,
        request,
        operator.id,
        "purchase_batch.adjusted",
        "purchase_batch",
        batch.id,
        body.reason,
        {
            "before": before,
            "minimum_viable_threshold_quantity": batch.minimum_viable_threshold_quantity,
            "deadline_at": batch.deadline_at.isoformat() if batch.deadline_at else None,
            "threshold_reached_by_adjustment": newly_reached,
        },
    )
    await session.commit()
    return _purchase_batch_response(batch)


@router.post("/purchase-batches/{batch_id}/commit", response_model=PurchaseBatchResponse)
async def commit_purchase_batch(
    batch_id: UUID,
    body: PurchaseBatchCommitBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> PurchaseBatchResponse:
    batch = await session.get(PurchaseBatch, batch_id, with_for_update=True)
    if batch is None:
        raise HTTPException(status_code=404, detail="purchase_batch_not_found")
    evidence = await session.get(EvidenceFile, body.evidence_file_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="evidence_file_not_found")
    already_committed = batch.status == "committed"
    try:
        batch = await commit_batch(
            session,
            batch=batch,
            operator_id=operator.id,
            evidence_file_id=evidence.id,
            commitment_reference=body.commitment_reference,
            reason=body.reason,
        )
    except PurchasingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not already_committed:
        _audit(
            session,
            request,
            operator.id,
            "purchase_batch.committed",
            "purchase_batch",
            batch.id,
            body.reason,
            {
                "offer_id": str(batch.offer_id),
                "allocated_quantity": batch.allocated_quantity,
                "evidence_file_id": str(evidence.id),
                "commitment_reference": batch.commitment_reference,
            },
        )
    await session.commit()
    return _purchase_batch_response(batch)


@router.post(
    "/suppliers/{supplier_id}/assurances",
    response_model=CreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_supplier_assurance(
    supplier_id: UUID,
    body: SupplierAssuranceBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> CreatedResponse:
    if await session.get(Supplier, supplier_id) is None:
        raise HTTPException(status_code=404, detail="supplier_not_found")
    if body.valid_until is not None and body.valid_until < body.valid_from:
        raise HTTPException(status_code=422, detail="invalid_assurance_validity")
    evidence_file = await session.get(EvidenceFile, body.evidence_file_id)
    if evidence_file is None:
        raise HTTPException(status_code=404, detail="evidence_file_not_found")
    assurance = SupplierAssurance(
        supplier_id=supplier_id,
        version=body.version,
        evidence_file_id=evidence_file.id,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        active=True,
        recorded_by_operator_id=operator.id,
    )
    session.add(assurance)
    await session.flush()
    _audit(
        session,
        request,
        operator.id,
        "supplier.assurance_recorded",
        "supplier",
        supplier_id,
        body.reason,
        {"assurance_id": str(assurance.id), "version": assurance.version},
    )
    await session.commit()
    return CreatedResponse(id=assurance.id)


@router.post(
    "/offers/{offer_id}/reference-evidence",
    response_model=CreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_reference_evidence(
    offer_id: UUID,
    body: ReferenceEvidenceBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> CreatedResponse:
    offer = await session.get(Offer, offer_id, with_for_update=True)
    if offer is None:
        raise HTTPException(status_code=404, detail="offer_not_found")
    evidence_file = await session.get(EvidenceFile, body.evidence_file_id)
    if evidence_file is None:
        raise HTTPException(status_code=404, detail="evidence_file_not_found")
    evidence = ReferencePriceEvidence(
        offer_id=offer.id,
        amount_irr=body.amount_irr,
        observed_at=body.observed_at,
        source_label=body.source_label,
        evidence_file_id=evidence_file.id,
        recorded_by_operator_id=operator.id,
    )
    session.add(evidence)
    offer.reference_price_irr = body.amount_irr
    offer.reference_price_reviewed_at = body.observed_at
    await session.flush()
    _audit(
        session,
        request,
        operator.id,
        "offer.reference_evidence_recorded",
        "offer",
        offer.id,
        body.reason,
        {
            "evidence_id": str(evidence.id),
            "amount_irr": evidence.amount_irr,
            "observed_at": evidence.observed_at.isoformat(),
        },
    )
    await session.commit()
    return CreatedResponse(id=evidence.id)


class ProductAlternativeCreateBody(BaseModel):
    source_product_id: UUID
    alternative_product_id: UUID
    rationale_fa: str = Field(min_length=5, max_length=1000)
    compatibility_notes_fa: str | None = Field(default=None, max_length=1000)
    rank: int = Field(default=0, ge=0, le=1000)
    reason: str = Field(min_length=5, max_length=1000)


class ProductAlternativeUpdateBody(BaseModel):
    rationale_fa: str = Field(min_length=5, max_length=1000)
    compatibility_notes_fa: str | None = Field(default=None, max_length=1000)
    rank: int = Field(default=0, ge=0, le=1000)
    reason: str = Field(min_length=5, max_length=1000)


class ProductAlternativeActionBody(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class OperatorProductAlternativeResponse(BaseModel):
    id: UUID
    source_product_id: UUID
    alternative_product_id: UUID
    status: str
    rank: int
    rationale_fa: str
    compatibility_notes_fa: str | None
    proposed_by_operator_id: UUID
    approved_by_operator_id: UUID | None
    approved_at: datetime | None
    retired_by_operator_id: UUID | None
    retired_at: datetime | None


def _operator_alternative_response(
    alternative: ProductAlternative,
) -> OperatorProductAlternativeResponse:
    return OperatorProductAlternativeResponse(
        id=alternative.id,
        source_product_id=alternative.source_product_id,
        alternative_product_id=alternative.alternative_product_id,
        status=alternative.status,
        rank=alternative.rank,
        rationale_fa=alternative.rationale_fa,
        compatibility_notes_fa=alternative.compatibility_notes_fa,
        proposed_by_operator_id=alternative.proposed_by_operator_id,
        approved_by_operator_id=alternative.approved_by_operator_id,
        approved_at=alternative.approved_at,
        retired_by_operator_id=alternative.retired_by_operator_id,
        retired_at=alternative.retired_at,
    )


@router.get(
    "/product-alternatives",
    response_model=list[OperatorProductAlternativeResponse],
)
async def list_product_alternatives(
    _: CurrentOperator,
    session: SessionDependency,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    source_product_id: UUID | None = None,
) -> list[OperatorProductAlternativeResponse]:
    if status_filter is not None and status_filter not in ("proposed", "approved", "retired"):
        raise HTTPException(status_code=422, detail="invalid_status_filter")
    query = select(ProductAlternative).order_by(ProductAlternative.created_at.desc())
    if status_filter is not None:
        query = query.where(ProductAlternative.status == status_filter)
    if source_product_id is not None:
        query = query.where(ProductAlternative.source_product_id == source_product_id)
    rows = list((await session.scalars(query.limit(200))).all())
    return [_operator_alternative_response(row) for row in rows]


@router.post(
    "/product-alternatives",
    response_model=CreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product_alternative(
    body: ProductAlternativeCreateBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> CreatedResponse:
    if body.source_product_id == body.alternative_product_id:
        raise HTTPException(status_code=422, detail="alternative_cannot_reference_itself")
    for product_id in (body.source_product_id, body.alternative_product_id):
        if await session.get(Product, product_id) is None:
            raise HTTPException(status_code=404, detail="product_not_found")
    existing = await session.scalar(
        select(ProductAlternative).where(
            ProductAlternative.source_product_id == body.source_product_id,
            ProductAlternative.alternative_product_id == body.alternative_product_id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="alternative_pair_already_exists")
    alternative = ProductAlternative(
        source_product_id=body.source_product_id,
        alternative_product_id=body.alternative_product_id,
        status="proposed",
        rank=body.rank,
        rationale_fa=body.rationale_fa,
        compatibility_notes_fa=body.compatibility_notes_fa,
        proposed_by_operator_id=operator.id,
    )
    session.add(alternative)
    await session.flush()
    _audit(
        session,
        request,
        operator.id,
        "product_alternative.created",
        "product_alternative",
        alternative.id,
        body.reason,
        {
            "source_product_id": str(body.source_product_id),
            "alternative_product_id": str(body.alternative_product_id),
            "rank": body.rank,
        },
    )
    await session.commit()
    return CreatedResponse(id=alternative.id)


@router.patch(
    "/product-alternatives/{alternative_id}",
    response_model=OperatorProductAlternativeResponse,
)
async def update_product_alternative(
    alternative_id: UUID,
    body: ProductAlternativeUpdateBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> OperatorProductAlternativeResponse:
    alternative = await session.get(ProductAlternative, alternative_id, with_for_update=True)
    if alternative is None:
        raise HTTPException(status_code=404, detail="product_alternative_not_found")
    if alternative.status == "retired":
        raise HTTPException(status_code=409, detail="product_alternative_retired")
    before_facts = {
        "rationale_fa": alternative.rationale_fa,
        "compatibility_notes_fa": alternative.compatibility_notes_fa,
        "rank": alternative.rank,
    }
    alternative.rationale_fa = body.rationale_fa
    alternative.compatibility_notes_fa = body.compatibility_notes_fa
    alternative.rank = body.rank
    await session.flush()
    record_operator_action(
        session,
        operator_identity_id=operator.id,
        action="product_alternative.updated",
        resource_type="product_alternative",
        resource_id=str(alternative.id),
        request_id=request_id_context.get(),
        reason=body.reason,
        before_facts=before_facts,
        after_facts={
            "rationale_fa": alternative.rationale_fa,
            "compatibility_notes_fa": alternative.compatibility_notes_fa,
            "rank": alternative.rank,
        },
        source_ip=request.client.host if request.client else None,
    )
    await session.commit()
    return _operator_alternative_response(alternative)


@router.post(
    "/product-alternatives/{alternative_id}/approve",
    response_model=OperatorProductAlternativeResponse,
)
async def approve_product_alternative(
    alternative_id: UUID,
    body: ProductAlternativeActionBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> OperatorProductAlternativeResponse:
    alternative = await session.get(ProductAlternative, alternative_id, with_for_update=True)
    if alternative is None:
        raise HTTPException(status_code=404, detail="product_alternative_not_found")
    if alternative.status == "retired":
        raise HTTPException(status_code=409, detail="product_alternative_retired")
    if alternative.status != "approved":
        alternative.status = "approved"
        alternative.approved_by_operator_id = operator.id
        alternative.approved_at = utc_now()
        await session.flush()
        _audit(
            session,
            request,
            operator.id,
            "product_alternative.approved",
            "product_alternative",
            alternative.id,
            body.reason,
            {"status": alternative.status, "approved_at": alternative.approved_at.isoformat()},
        )
    await session.commit()
    return _operator_alternative_response(alternative)


@router.post(
    "/product-alternatives/{alternative_id}/retire",
    response_model=OperatorProductAlternativeResponse,
)
async def retire_product_alternative(
    alternative_id: UUID,
    body: ProductAlternativeActionBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> OperatorProductAlternativeResponse:
    alternative = await session.get(ProductAlternative, alternative_id, with_for_update=True)
    if alternative is None:
        raise HTTPException(status_code=404, detail="product_alternative_not_found")
    if alternative.status != "retired":
        alternative.status = "retired"
        alternative.retired_by_operator_id = operator.id
        alternative.retired_at = utc_now()
        await session.flush()
        _audit(
            session,
            request,
            operator.id,
            "product_alternative.retired",
            "product_alternative",
            alternative.id,
            body.reason,
            {"status": alternative.status, "retired_at": alternative.retired_at.isoformat()},
        )
    await session.commit()
    return _operator_alternative_response(alternative)


@router.post("/order-lines/{line_id}/confirm-sourced", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_sourced_unit(
    line_id: UUID,
    body: SourcedUnitConfirmationBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> None:
    row = (
        await session.execute(
            select(OrderLine, Order, Offer, Supplier)
            .join(Order, Order.id == OrderLine.order_id)
            .join(Offer, Offer.id == OrderLine.offer_id)
            .join(Supplier, Supplier.id == Offer.supplier_id)
            .where(OrderLine.id == line_id)
            .with_for_update(of=OrderLine)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="order_line_not_found")
    line, order, offer, supplier = row
    if order.delivery_commitment_at is None:
        raise HTTPException(status_code=409, detail="order_has_no_delivery_commitment")
    minimum_date = add_months(
        order.delivery_commitment_at.date(), offer.minimum_shelf_life_months
    )
    if body.exact_expiry_date < minimum_date:
        raise HTTPException(status_code=409, detail="shelf_life_guarantee_not_met")
    assurance = await session.scalar(
        select(SupplierAssurance).where(
            SupplierAssurance.supplier_id == supplier.id,
            SupplierAssurance.active.is_(True),
            SupplierAssurance.valid_from <= date.today(),
            (SupplierAssurance.valid_until.is_(None))
            | (SupplierAssurance.valid_until >= date.today()),
        )
    )
    if assurance is None:
        raise HTTPException(status_code=409, detail="active_supplier_assurance_required")
    existing = await session.scalar(
        select(SourcedUnitEvidence).where(SourcedUnitEvidence.order_line_id == line.id)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="sourced_unit_already_confirmed")
    evidence = SourcedUnitEvidence(
        order_line_id=line.id,
        exact_expiry_date=body.exact_expiry_date,
        supplier_country_snapshot=supplier.country_code,
        authenticity_basis="supplier_verified",
        supplier_assurance_id=assurance.id,
        confirmed_at=utc_now(),
        recorded_by_operator_id=operator.id,
    )
    session.add(evidence)
    await session.flush()
    _audit(
        session,
        request,
        operator.id,
        "order_line.sourcing_confirmed",
        "order_line",
        line.id,
        body.reason,
        {
            "sourced_unit_evidence_id": str(evidence.id),
            "exact_expiry_date": body.exact_expiry_date.isoformat(),
            "supplier_country": supplier.country_code,
            "authenticity_basis": "supplier_verified",
        },
    )
    await session.commit()


class ShelfLifeExceptionProposeBody(BaseModel):
    proposed_exact_expiry_date: date
    additional_discount_irr: int = Field(ge=0)
    evidence_file_id: UUID
    reason: str = Field(min_length=5, max_length=1000)


class OperatorShelfLifeExceptionResponse(BaseModel):
    id: UUID
    order_line_id: UUID
    proposed_exact_expiry_date: date
    additional_discount_irr: int
    reason: str
    evidence_file_id: UUID
    proposed_by_operator_id: UUID
    proposed_at: datetime
    respond_by: datetime
    status: str
    responded_at: datetime | None
    responded_by_customer_identity_id: UUID | None
    refund_status: str
    refund_amount_irr: int | None
    refund_attested_at: datetime | None
    refund_attested_by_operator_id: UUID | None
    refund_reference: str | None


class RefundAttestBody(BaseModel):
    evidence_file_id: UUID
    reference: str | None = Field(default=None, max_length=300)
    reason: str = Field(min_length=5, max_length=1000)


def _shelf_life_exception_response(
    exception: ShelfLifeException,
) -> OperatorShelfLifeExceptionResponse:
    return OperatorShelfLifeExceptionResponse(
        id=exception.id,
        order_line_id=exception.order_line_id,
        proposed_exact_expiry_date=exception.proposed_exact_expiry_date,
        additional_discount_irr=exception.additional_discount_irr,
        reason=exception.reason,
        evidence_file_id=exception.evidence_file_id,
        proposed_by_operator_id=exception.proposed_by_operator_id,
        proposed_at=exception.proposed_at,
        respond_by=exception.respond_by,
        status=exception.status,
        responded_at=exception.responded_at,
        responded_by_customer_identity_id=exception.responded_by_customer_identity_id,
        refund_status=exception.refund_status,
        refund_amount_irr=exception.refund_amount_irr,
        refund_attested_at=exception.refund_attested_at,
        refund_attested_by_operator_id=exception.refund_attested_by_operator_id,
        refund_reference=exception.refund_reference,
    )


@router.post(
    "/order-lines/{line_id}/shelf-life-exceptions",
    response_model=OperatorShelfLifeExceptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def propose_order_line_shelf_life_exception(
    line_id: UUID,
    body: ShelfLifeExceptionProposeBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> OperatorShelfLifeExceptionResponse:
    row = (
        await session.execute(
            select(OrderLine, Order, Offer)
            .join(Order, Order.id == OrderLine.order_id)
            .join(Offer, Offer.id == OrderLine.offer_id)
            .where(OrderLine.id == line_id)
            .with_for_update(of=OrderLine)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="order_line_not_found")
    line, order, offer = row
    evidence = await session.get(EvidenceFile, body.evidence_file_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="evidence_file_not_found")
    try:
        exception = await propose_shelf_life_exception(
            session,
            order_line=line,
            order=order,
            minimum_shelf_life_months=offer.minimum_shelf_life_months,
            operator_id=operator.id,
            proposed_exact_expiry_date=body.proposed_exact_expiry_date,
            additional_discount_irr=body.additional_discount_irr,
            reason=body.reason,
            evidence_file_id=evidence.id,
        )
    except ShelfLifeExceptionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(
        session,
        request,
        operator.id,
        "shelf_life_exception.proposed",
        "order_line",
        line.id,
        body.reason,
        {
            "shelf_life_exception_id": str(exception.id),
            "proposed_exact_expiry_date": body.proposed_exact_expiry_date.isoformat(),
            "additional_discount_irr": body.additional_discount_irr,
            "respond_by": exception.respond_by.isoformat(),
        },
    )
    await session.commit()
    return _shelf_life_exception_response(exception)


@router.get("/shelf-life-exceptions", response_model=list[OperatorShelfLifeExceptionResponse])
async def list_shelf_life_exceptions(
    _: CurrentOperator,
    session: SessionDependency,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[OperatorShelfLifeExceptionResponse]:
    if status_filter is not None and status_filter not in (
        "proposed",
        "accepted",
        "declined",
        "expired",
    ):
        raise HTTPException(status_code=422, detail="invalid_status_filter")
    query = select(ShelfLifeException).order_by(ShelfLifeException.proposed_at.desc())
    if status_filter is not None:
        query = query.where(ShelfLifeException.status == status_filter)
    rows = list((await session.scalars(query.limit(200))).all())
    return [_shelf_life_exception_response(row) for row in rows]


@router.get(
    "/shelf-life-exceptions/{exception_id}", response_model=OperatorShelfLifeExceptionResponse
)
async def get_shelf_life_exception(
    exception_id: UUID, _: CurrentOperator, session: SessionDependency
) -> OperatorShelfLifeExceptionResponse:
    exception = await session.get(ShelfLifeException, exception_id)
    if exception is None:
        raise HTTPException(status_code=404, detail="shelf_life_exception_not_found")
    return _shelf_life_exception_response(exception)


@router.post(
    "/shelf-life-exceptions/{exception_id}/attest-refund",
    response_model=OperatorShelfLifeExceptionResponse,
)
async def attest_shelf_life_exception_refund(
    exception_id: UUID,
    body: RefundAttestBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> OperatorShelfLifeExceptionResponse:
    exception = await session.get(ShelfLifeException, exception_id, with_for_update=True)
    if exception is None:
        raise HTTPException(status_code=404, detail="shelf_life_exception_not_found")
    evidence = await session.get(EvidenceFile, body.evidence_file_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="evidence_file_not_found")
    already_attested = exception.refund_status == "operator_attested"
    try:
        attest_refund(
            exception,
            operator_id=operator.id,
            evidence_id=evidence.id,
            reference=body.reference,
        )
    except RefundAttestationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not already_attested:
        _audit(
            session,
            request,
            operator.id,
            "shelf_life_exception.refund_attested",
            "shelf_life_exception",
            exception.id,
            body.reason,
            {
                "refund_amount_irr": exception.refund_amount_irr,
                "evidence_file_id": str(evidence.id),
            },
        )
    await session.commit()
    return _shelf_life_exception_response(exception)


@router.post(
    "/order-cancellations/{cancellation_id}/attest-refund",
    response_model=OrderCancellationResponse,
)
async def attest_order_cancellation_refund(
    cancellation_id: UUID,
    body: RefundAttestBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> OrderCancellationResponse:
    cancellation = await session.get(OrderCancellation, cancellation_id, with_for_update=True)
    if cancellation is None:
        raise HTTPException(status_code=404, detail="order_cancellation_not_found")
    evidence = await session.get(EvidenceFile, body.evidence_file_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="evidence_file_not_found")
    already_attested = cancellation.refund_status == "operator_attested"
    try:
        attest_refund(
            cancellation,
            operator_id=operator.id,
            evidence_id=evidence.id,
            reference=body.reference,
        )
    except RefundAttestationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not already_attested:
        _audit(
            session,
            request,
            operator.id,
            "order_cancellation.refund_attested",
            "order_cancellation",
            cancellation.id,
            body.reason,
            {
                "refund_amount_irr": cancellation.refund_amount_irr,
                "evidence_file_id": str(evidence.id),
            },
        )
    await session.commit()
    return OrderCancellationResponse(
        order_id=cancellation.order_id,
        status="cancelled",
        cancelled_at=cancellation.created_at,
        reason=cancellation.reason,
        refund_amount_irr=cancellation.refund_amount_irr,
        refund_status=cancellation.refund_status,
    )


class ReservationReconfirmBody(BaseModel):
    reconfirmed_price_irr: int = Field(gt=0)
    reconfirmed_available: bool
    reason: str = Field(min_length=5, max_length=1000)


class ReservationDeclineBody(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class OperatorReservationResponse(BaseModel):
    id: UUID
    customer_identity_id: UUID
    household_id: UUID
    offer_id: UUID
    quantity: int
    requested_price_irr: int
    requested_at: datetime
    operator_review_by: datetime
    status: str
    reconfirmed_price_irr: int | None
    reconfirmed_available: bool | None
    proposed_at: datetime | None
    customer_respond_by: datetime | None
    responded_at: datetime | None
    decline_reason: str | None
    order_id: UUID | None
    converted_at: datetime | None


def _operator_reservation_response(reservation: Reservation) -> OperatorReservationResponse:
    return OperatorReservationResponse(
        id=reservation.id,
        customer_identity_id=reservation.customer_identity_id,
        household_id=reservation.household_id,
        offer_id=reservation.offer_id,
        quantity=reservation.quantity,
        requested_price_irr=reservation.requested_price_irr,
        requested_at=reservation.requested_at,
        operator_review_by=reservation.operator_review_by,
        status=reservation.status,
        reconfirmed_price_irr=reservation.reconfirmed_price_irr,
        reconfirmed_available=reservation.reconfirmed_available,
        proposed_at=reservation.proposed_at,
        customer_respond_by=reservation.customer_respond_by,
        responded_at=reservation.responded_at,
        decline_reason=reservation.decline_reason,
        order_id=reservation.order_id,
        converted_at=reservation.converted_at,
    )


@router.get("/reservations", response_model=list[OperatorReservationResponse])
async def list_reservations(
    _: CurrentOperator,
    session: SessionDependency,
    settings: SettingsDependency,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[OperatorReservationResponse]:
    if not settings.reserve_now_enabled:
        raise HTTPException(status_code=409, detail="reserve_now_disabled")
    valid_statuses = (
        "requested",
        "proposed",
        "converted",
        "customer_declined",
        "operator_declined",
        "expired",
    )
    if status_filter is not None and status_filter not in valid_statuses:
        raise HTTPException(status_code=422, detail="invalid_status_filter")
    query = select(Reservation).order_by(Reservation.requested_at.desc())
    if status_filter is not None:
        query = query.where(Reservation.status == status_filter)
    rows = list((await session.scalars(query.limit(200))).all())
    return [_operator_reservation_response(row) for row in rows]


@router.get("/reservations/{reservation_id}", response_model=OperatorReservationResponse)
async def get_reservation(
    reservation_id: UUID,
    _: CurrentOperator,
    session: SessionDependency,
    settings: SettingsDependency,
) -> OperatorReservationResponse:
    if not settings.reserve_now_enabled:
        raise HTTPException(status_code=409, detail="reserve_now_disabled")
    reservation = await session.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="reservation_not_found")
    return _operator_reservation_response(reservation)


@router.post(
    "/reservations/{reservation_id}/reconfirm-and-propose",
    response_model=OperatorReservationResponse,
)
async def reconfirm_and_propose_reservation_endpoint(
    reservation_id: UUID,
    body: ReservationReconfirmBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
    settings: SettingsDependency,
) -> OperatorReservationResponse:
    if not settings.reserve_now_enabled:
        raise HTTPException(status_code=409, detail="reserve_now_disabled")
    reservation = await session.get(Reservation, reservation_id, with_for_update=True)
    if reservation is None:
        raise HTTPException(status_code=404, detail="reservation_not_found")
    already_proposed = reservation.status == "proposed"
    try:
        reservation = await reconfirm_and_propose_reservation(
            session,
            reservation=reservation,
            operator_id=operator.id,
            reconfirmed_price_irr=body.reconfirmed_price_irr,
            reconfirmed_available=body.reconfirmed_available,
            reason=body.reason,
        )
    except ReservationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not already_proposed:
        _audit(
            session,
            request,
            operator.id,
            "reservation.reconfirmed_and_proposed",
            "reservation",
            reservation.id,
            body.reason,
            {
                "reconfirmed_price_irr": body.reconfirmed_price_irr,
                "reconfirmed_available": body.reconfirmed_available,
                "customer_respond_by": (
                    reservation.customer_respond_by.isoformat()
                    if reservation.customer_respond_by
                    else None
                ),
            },
        )
    await session.commit()
    return _operator_reservation_response(reservation)


@router.post("/reservations/{reservation_id}/decline", response_model=OperatorReservationResponse)
async def operator_decline_reservation_endpoint(
    reservation_id: UUID,
    body: ReservationDeclineBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
    settings: SettingsDependency,
) -> OperatorReservationResponse:
    if not settings.reserve_now_enabled:
        raise HTTPException(status_code=409, detail="reserve_now_disabled")
    reservation = await session.get(Reservation, reservation_id, with_for_update=True)
    if reservation is None:
        raise HTTPException(status_code=404, detail="reservation_not_found")
    already_declined = reservation.status == "operator_declined"
    try:
        reservation = await operator_decline_reservation(
            session, reservation=reservation, operator_id=operator.id, reason=body.reason
        )
    except ReservationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not already_declined:
        _audit(
            session,
            request,
            operator.id,
            "reservation.operator_declined",
            "reservation",
            reservation.id,
            body.reason,
            {"reason": body.reason},
        )
    await session.commit()
    return _operator_reservation_response(reservation)


@router.post(
    "/notification-templates",
    response_model=CreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_template(
    body: NotificationTemplateBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> CreatedResponse:
    _validate_template_fields(body.event_key, body.body_fa)
    if body.activate:
        active = list(
            (
                await session.scalars(
                    select(NotificationTemplate).where(
                        NotificationTemplate.event_key == body.event_key,
                        NotificationTemplate.channel == body.channel,
                        NotificationTemplate.active.is_(True),
                    )
                )
            ).all()
        )
        for item in active:
            item.active = False
    template = NotificationTemplate(
        event_key=body.event_key,
        channel=body.channel,
        version=body.version,
        body_fa=body.body_fa,
        active=body.activate,
    )
    session.add(template)
    await session.flush()
    _audit(
        session,
        request,
        operator.id,
        "notification_template.created",
        "notification_template",
        template.id,
        body.reason,
        {"event_key": template.event_key, "version": template.version, "active": template.active},
    )
    await session.commit()
    return CreatedResponse(id=template.id)


@router.post(
    "/evidence-files",
    response_model=CreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_evidence_file(
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
    filename: Annotated[str, Header(alias="X-Filename", min_length=1, max_length=300)],
    reason: Annotated[str, Header(alias="X-Reason", min_length=5, max_length=1000)],
) -> CreatedResponse:
    allowed_types = {"application/pdf", "image/jpeg", "image/png", "text/plain"}
    media_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if media_type not in allowed_types:
        raise HTTPException(status_code=415, detail="unsupported_evidence_media_type")
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="evidence_file_too_large")
    content_buffer = bytearray()
    async for chunk in request.stream():
        content_buffer.extend(chunk)
        if len(content_buffer) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="evidence_file_too_large")
    content = bytes(content_buffer)
    if not content:
        raise HTTPException(status_code=413, detail="invalid_evidence_file_size")
    safe_name = _safe_filename(filename)
    key = f"evidence/{uuid4()}/{safe_name}"
    from app.main import get_storage

    stored = await get_storage().put_bytes(key, content)
    evidence = EvidenceFile(
        storage_key=stored.key,
        original_filename=safe_name,
        media_type=media_type,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
        uploaded_by_operator_id=operator.id,
    )
    session.add(evidence)
    await session.flush()
    _audit(
        session,
        request,
        operator.id,
        "evidence_file.uploaded",
        "evidence_file",
        evidence.id,
        reason,
        {
            "storage_key": stored.key,
            "size_bytes": stored.size_bytes,
            "checksum_sha256": stored.checksum_sha256,
        },
    )
    await session.commit()
    return CreatedResponse(id=evidence.id)


@router.get("/evidence-files/{evidence_id}", response_class=FileResponse)
async def download_evidence_file(
    evidence_id: UUID,
    _: CurrentOperator,
    session: SessionDependency,
) -> FileResponse:
    evidence = await session.get(EvidenceFile, evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="evidence_file_not_found")
    from app.main import get_storage

    path = get_storage().path_for(evidence.storage_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="evidence_file_missing_from_storage")
    return FileResponse(
        path,
        media_type=evidence.media_type,
        filename=evidence.original_filename,
    )


@router.get("/telemetry", response_model=dict[str, int])
async def operational_telemetry(_: CurrentOperator, session: SessionDependency) -> dict[str, int]:
    now = utc_now()
    metrics = {
        "outbox_pending": await session.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.published_at.is_(None))
        ),
        "outbox_failed": await session.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.status == "failed")
        ),
        "outbox_dead_letter": await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.status == "dead_letter")
        ),
        "notifications_failed": await session.scalar(
            select(func.count()).select_from(Notification).where(Notification.status == "failed")
        ),
        "orders_overdue": await session.scalar(
            select(func.count())
            .select_from(Order)
            .where(
                Order.delivery_commitment_at < now,
                Order.status.not_in(("delivered", "cancelled", "failed")),
            )
        ),
        "sourcing_pending": await session.scalar(
            select(func.count()).select_from(SourcingJob).where(SourcingJob.status == "pending")
        ),
        "resolutions_awaiting_policy": await session.scalar(
            select(func.count())
            .select_from(OrderResolution)
            .where(OrderResolution.state == "awaiting_policy")
        ),
    }
    return {key: int(value or 0) for key, value in metrics.items()}


class OutboxEventResponse(BaseModel):
    id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: str
    status: str
    disposition: str
    attempts: int
    occurred_at: datetime
    available_at: datetime
    published_at: datetime | None
    last_error: str | None


class OutboxEventListResponse(BaseModel):
    items: list[OutboxEventResponse]
    has_more: bool


class OutboxReplayBody(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


def _outbox_event_response(record: OutboxEvent) -> OutboxEventResponse:
    return OutboxEventResponse(
        id=record.id,
        event_type=record.event_type,
        aggregate_type=record.aggregate_type,
        aggregate_id=record.aggregate_id,
        status=record.status,
        disposition=record.disposition,
        attempts=record.attempts,
        occurred_at=record.occurred_at,
        available_at=record.available_at,
        published_at=record.published_at,
        last_error=record.last_error,
    )


@router.get("/outbox/events", response_model=OutboxEventListResponse)
async def list_outbox_events(
    _: CurrentOperator,
    session: SessionDependency,
    status_filter: Annotated[
        Literal["pending", "failed", "dead_letter", "published"], Query(alias="status")
    ] = "dead_letter",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> OutboxEventListResponse:
    rows = list(
        (
            await session.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.status == status_filter)
                .order_by(OutboxEvent.occurred_at.desc())
                .offset(offset)
                .limit(limit + 1)
            )
        ).all()
    )
    has_more = len(rows) > limit
    return OutboxEventListResponse(
        items=[_outbox_event_response(row) for row in rows[:limit]], has_more=has_more
    )


@router.post("/outbox/events/{event_id}/replay", response_model=OutboxEventResponse)
async def replay_outbox_event(
    event_id: UUID,
    body: OutboxReplayBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> OutboxEventResponse:
    # Operator replay procedure: a failed/dead-lettered event is reset to
    # pending so the outbox worker's normal dispatch loop picks it back up
    # on its next poll -- this does not re-invoke handlers directly, which
    # keeps replay subject to the same disposition/handler-lookup rules
    # (and any handler-side idempotency) as the original dispatch attempt.
    record = await session.get(OutboxEvent, event_id, with_for_update=True)
    if record is None:
        raise HTTPException(status_code=404, detail="outbox_event_not_found")
    if record.status not in ("failed", "dead_letter"):
        raise HTTPException(status_code=409, detail="outbox_event_not_replayable")
    previous_status = record.status
    record.status = "pending"
    record.available_at = utc_now()
    record.claimed_until = None
    record.attempts = 0
    record.last_error = None
    _audit(
        session,
        request,
        operator.id,
        "outbox_event.replayed",
        "outbox_event",
        event_id,
        body.reason,
        {"event_type": record.event_type, "previous_status": previous_status},
    )
    await session.commit()
    return _outbox_event_response(record)


class KPIResultResponse(BaseModel):
    key: str
    name: str
    description: str
    version: int
    computable: bool
    numerator: float | None
    denominator: float | None
    value: float | None
    unit: str
    currency: str | None
    data_limitation: str | None
    window: str
    timezone: str
    status_inclusion: str
    late_event_handling: str
    validation_query: str


def _kpi_response(definition: KPIDefinition, result: KPIResult) -> KPIResultResponse:
    return KPIResultResponse(
        key=definition.key,
        name=definition.name,
        description=definition.description,
        version=definition.version,
        computable=result.computable,
        numerator=result.numerator,
        denominator=result.denominator,
        value=result.value,
        unit=result.unit,
        currency=definition.currency,
        data_limitation=result.data_limitation,
        window=definition.window,
        timezone=definition.timezone,
        status_inclusion=definition.status_inclusion,
        late_event_handling=definition.late_event_handling,
        validation_query=definition.validation_query,
    )


@router.get("/kpis", response_model=list[KPIResultResponse])
async def list_kpis(
    _: CurrentOperator,
    session: SessionDependency,
    window_start: datetime,
    window_end: datetime,
) -> list[KPIResultResponse]:
    if window_end <= window_start:
        raise HTTPException(status_code=422, detail="window_end_must_be_after_window_start")
    results = await compute_all_kpis(session, window_start=window_start, window_end=window_end)
    return [
        _kpi_response(KPI_REGISTRY[result.key], result)
        for result in results
    ]


@router.get("/kpis/{key}", response_model=KPIResultResponse)
async def get_kpi(
    key: str,
    _: CurrentOperator,
    session: SessionDependency,
    window_start: datetime,
    window_end: datetime,
) -> KPIResultResponse:
    if key not in KPI_REGISTRY:
        raise HTTPException(status_code=404, detail="kpi_not_found")
    if window_end <= window_start:
        raise HTTPException(status_code=422, detail="window_end_must_be_after_window_start")
    result = await compute_kpi(session, key, window_start=window_start, window_end=window_end)
    return _kpi_response(KPI_REGISTRY[key], result)


@router.get("/audit/export")
async def export_audit_log(
    _: CurrentOperator,
    session: SessionDependency,
    limit: int = 10_000,
) -> Response:
    if not 1 <= limit <= 10_000:
        raise HTTPException(status_code=422, detail="audit_export_limit_out_of_range")
    rows = list(
        (
            await session.scalars(
                select(OperatorAuditLog).order_by(OperatorAuditLog.sequence.desc()).limit(limit)
            )
        ).all()
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "sequence",
            "occurred_at",
            "operator_identity_id",
            "action",
            "resource_type",
            "resource_id",
            "reason",
            "request_id",
            "source_ip",
            "before_facts",
            "after_facts",
        ]
    )
    for item in reversed(rows):
        writer.writerow(
            [
                item.sequence,
                item.occurred_at.isoformat(),
                item.operator_identity_id,
                item.action,
                item.resource_type,
                item.resource_id,
                item.reason,
                item.request_id,
                item.source_ip,
                json.dumps(item.before_facts, ensure_ascii=False, sort_keys=True),
                json.dumps(item.after_facts, ensure_ascii=False, sort_keys=True),
            ]
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=operator-audit.csv"},
    )


@router.get("/privacy/requests", response_model=list[dict[str, object]])
async def list_privacy_requests(
    _: CurrentOperator, session: SessionDependency
) -> list[dict[str, object]]:
    requests = list(
        (
            await session.scalars(
                select(PrivacyRequest)
                .where(PrivacyRequest.status.in_(("requested", "awaiting_policy")))
                .order_by(PrivacyRequest.created_at)
                .limit(500)
            )
        ).all()
    )
    return [
        {
            "id": item.id,
            "identity_id": item.identity_id,
            "request_type": item.request_type,
            "status": item.status,
            "reason": item.reason,
            "created_at": item.created_at,
        }
        for item in requests
    ]


@router.get("/webhooks/failed", response_model=list[dict[str, object]])
async def list_failed_webhooks(
    _: CurrentOperator,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, object]]:
    events = list(
        (
            await session.scalars(
                select(WebhookInboxEvent)
                .where(WebhookInboxEvent.processing_status == "failed")
                .order_by(WebhookInboxEvent.received_at)
                .limit(limit)
            )
        ).all()
    )
    return [
        {
            "id": item.id,
            "provider": item.provider,
            "provider_event_id": item.provider_event_id,
            "event_type": item.event_type,
            "received_at": item.received_at,
            "last_error": item.last_error,
        }
        for item in events
    ]


@router.post("/webhooks/{event_id}/replay", status_code=status.HTTP_202_ACCEPTED)
async def replay_failed_webhook(
    event_id: UUID,
    body: WebhookReplayBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> dict[str, str]:
    event = await session.get(WebhookInboxEvent, event_id, with_for_update=True)
    if event is None:
        raise HTTPException(status_code=404, detail="webhook_not_found")
    if event.processing_status != "failed" or not event.signature_valid:
        raise HTTPException(status_code=409, detail="webhook_not_replayable")
    previous_error = event.last_error
    event.processing_status = "received"
    event.processed_at = None
    event.last_error = None
    _audit(
        session,
        request,
        operator.id,
        "webhook.replay_requested",
        "webhook_inbox_event",
        event.id,
        body.reason,
        {"provider": event.provider, "previous_error": previous_error},
    )
    await session.commit()
    return {"status": "queued"}


@router.post(
    "/body-assessments/{assessment_id}/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def confirm_body_assessment(
    assessment_id: UUID,
    body: BodyAssessmentConfirmationBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> None:
    assessment = await session.get(BodyAssessment, assessment_id, with_for_update=True)
    if assessment is None:
        raise HTTPException(status_code=404, detail="body_assessment_not_found")
    if assessment.veterinarian_confirmed_at is not None:
        raise HTTPException(status_code=409, detail="body_assessment_already_confirmed")
    evidence = await session.get(EvidenceFile, body.evidence_file_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="confirmation_evidence_not_found")
    assessment.assessment_source = "veterinarian_confirmed"
    assessment.veterinarian_name = body.veterinarian_name
    assessment.veterinarian_credential = body.veterinarian_credential
    assessment.confirmed_by_operator_id = operator.id
    assessment.veterinarian_confirmed_at = utc_now()
    assessment.confirmation_evidence_file_id = evidence.id
    _audit(
        session,
        request,
        operator.id,
        "body_assessment.veterinary_confirmation_recorded",
        "body_assessment",
        assessment.id,
        body.reason,
        {
            "veterinarian_name": body.veterinarian_name,
            "veterinarian_credential": body.veterinarian_credential,
            "evidence_file_id": str(evidence.id),
        },
    )
    await session.commit()


@router.post("/privacy/requests/{request_id}/disable", status_code=status.HTTP_204_NO_CONTENT)
async def execute_account_disablement(
    request_id: UUID,
    body: PrivacyDecisionBody,
    http_request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> None:
    privacy_request = await session.get(PrivacyRequest, request_id, with_for_update=True)
    if privacy_request is None:
        raise HTTPException(status_code=404, detail="privacy_request_not_found")
    if privacy_request.request_type != "disable" or privacy_request.status != "requested":
        raise HTTPException(status_code=409, detail="privacy_request_cannot_be_disabled")
    identity = await session.get(AuthIdentity, privacy_request.identity_id, with_for_update=True)
    if identity is None:
        raise HTTPException(status_code=404, detail="identity_not_found")
    identity.status = "disabled"
    sessions = list(
        (
            await session.scalars(
                select(AuthSession).where(
                    AuthSession.identity_id == identity.id,
                    AuthSession.revoked_at.is_(None),
                )
            )
        ).all()
    )
    now = utc_now()
    for auth_session in sessions:
        auth_session.revoked_at = now
    privacy_request.status = "completed"
    privacy_request.completed_at = now
    privacy_request.result_facts = {"sessions_revoked": len(sessions)}
    _audit(
        session,
        http_request,
        operator.id,
        "identity.disabled",
        "identity",
        identity.id,
        body.reason,
        {"status": "disabled", "sessions_revoked": len(sessions)},
    )
    await session.commit()


@router.post("/payments/{attempt_id}/reconcile", response_model=ReconciliationResponse)
async def reconcile_payment(
    attempt_id: UUID,
    body: ReconciliationBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ReconciliationResponse:
    try:
        gateway = build_payment_gateway(settings)
    except PaymentProviderNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail="payment_provider_not_configured") from exc
    try:
        result = await PaymentService().reconcile(session, gateway, attempt_id=attempt_id)
    except PaymentWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ZarinpalError as exc:
        raise HTTPException(status_code=502, detail="payment_reconciliation_failed") from exc
    finally:
        await gateway.aclose()
    _audit(
        session,
        request,
        operator.id,
        "payment.reconciled",
        "payment_attempt",
        attempt_id,
        body.reason,
        {"state": result.state, "order_id": str(result.order_id)},
    )
    await session.commit()
    return ReconciliationResponse(state=result.state, order_id=result.order_id)


@router.post("/orders/{order_id}/deliver", response_model=DeliveryResponse)
async def deliver_order(
    order_id: UUID,
    body: DeliverOrderBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> DeliveryResponse:
    order = await session.get(Order, order_id, with_for_update=True)
    if order is None:
        raise HTTPException(status_code=404, detail="order_not_found")
    if order.status != "delivered":
        try:
            event = apply_fulfillment_transition(
                order,
                event_type="delivered",
                operator_identity_id=operator.id,
                reason=body.reason,
            )
        except FulfillmentTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        session.add(event)
    try:
        units = await project_delivered_order(
            session, order_id=order_id, household_id=body.household_id
        )
    except DeliveryProjectionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(
        session,
        request,
        operator.id,
        "order.delivered",
        "order",
        order_id,
        body.reason,
        {"inventory_unit_ids": [str(unit.id) for unit in units]},
    )
    await session.commit()
    return DeliveryResponse(inventory_unit_ids=[unit.id for unit in units])


@router.post("/orders/{order_id}/fulfillment", status_code=status.HTTP_204_NO_CONTENT)
async def transition_fulfillment(
    order_id: UUID,
    body: FulfillmentBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> None:
    order = await session.get(Order, order_id, with_for_update=True)
    if order is None:
        raise HTTPException(status_code=404, detail="order_not_found")
    try:
        event = apply_fulfillment_transition(
            order,
            event_type=body.event_type,
            operator_identity_id=operator.id,
            reason=body.reason,
        )
    except FulfillmentTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.add(event)
    _audit(
        session,
        request,
        operator.id,
        f"order.{body.event_type}",
        "order",
        order.id,
        body.reason,
        {"status": order.status},
    )
    await session.commit()


@router.post(
    "/journey-definitions",
    response_model=CreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_journey_definition(
    body: JourneyDefinitionBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> CreatedResponse:
    definition = JourneyDefinition(
        key=body.key,
        version=body.version,
        title_fa=body.title_fa,
        content=_journey_content_to_storage(body.content),
        approval_status="draft",
    )
    session.add(definition)
    await session.flush()
    _audit(
        session,
        request,
        operator.id,
        "journey_definition.created",
        "journey_definition",
        definition.id,
        body.reason,
        {"key": definition.key, "version": definition.version, "status": "draft"},
    )
    await session.commit()
    return CreatedResponse(id=definition.id)


@router.post("/journey-definitions/{definition_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def approve_journey_definition(
    definition_id: UUID,
    body: JourneyApprovalBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> None:
    definition = await session.get(JourneyDefinition, definition_id, with_for_update=True)
    if definition is None:
        raise HTTPException(status_code=404, detail="journey_definition_not_found")
    if definition.approval_status != "draft":
        raise HTTPException(status_code=409, detail="only_draft_content_can_be_approved")
    if not valid_journey_content(definition.content):
        raise HTTPException(status_code=422, detail="approved_journey_content_required")
    definition.approval_status = "approved"
    definition.approved_by = body.approved_by
    definition.approved_at = utc_now()
    _audit(
        session,
        request,
        operator.id,
        "journey_definition.approved",
        "journey_definition",
        definition.id,
        body.reason,
        {"approved_by": body.approved_by, "status": "approved"},
    )
    await session.commit()


@router.post("/orders/{order_id}/late-credit", response_model=LateCreditResponse)
async def issue_late_credit(
    order_id: UUID,
    body: LateCreditBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> LateCreditResponse:
    try:
        credit = await grant_late_delivery_credit(session, order_id=order_id)
    except WalletError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(
        session,
        request,
        operator.id,
        "wallet.late_delivery_credit",
        "order",
        order_id,
        body.reason,
        {"credit_id": str(credit.id), "amount_irr": credit.original_amount_irr},
    )
    await session.commit()
    return LateCreditResponse(
        credit_id=credit.id,
        amount_irr=credit.original_amount_irr,
        expires_at=credit.expires_at,
    )


@router.post(
    "/orders/{order_id}/resolutions",
    response_model=CreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def propose_resolution(
    order_id: UUID,
    body: ResolutionBody,
    request: Request,
    operator: CurrentOperator,
    session: SessionDependency,
) -> CreatedResponse:
    if await session.get(Order, order_id) is None:
        raise HTTPException(status_code=404, detail="order_not_found")
    resolution = OrderResolution(
        order_id=order_id,
        resolution_type=body.resolution_type,
        state="awaiting_policy",
        requested_by_operator_id=operator.id,
        reason=body.reason,
        proposed_facts=body.proposed_facts,
    )
    session.add(resolution)
    await session.flush()
    _audit(
        session,
        request,
        operator.id,
        "order.resolution_proposed",
        "order_resolution",
        resolution.id,
        body.reason,
        {
            "resolution_type": resolution.resolution_type,
            "state": "awaiting_policy",
        },
    )
    await session.commit()
    return CreatedResponse(id=resolution.id)


@router.get("/customers/{identity_id}/overview", response_model=dict[str, object])
async def customer_overview(
    identity_id: UUID,
    _: CurrentOperator,
    session: SessionDependency,
) -> dict[str, object]:
    memberships = list(
        (
            await session.scalars(
                select(HouseholdMembership).where(HouseholdMembership.identity_id == identity_id)
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
    order_ids = [order.id for order in orders]
    payment_count = await session.scalar(
        select(func.count())
        .select_from(PaymentAttempt)
        .where(PaymentAttempt.order_id.in_(order_ids))
    )
    inventory_count = await session.scalar(
        select(func.count())
        .select_from(InventoryUnit)
        .where(InventoryUnit.household_id.in_(household_ids))
    )
    pet_ids = [pet.id for pet in pets]
    journey_count = await session.scalar(
        select(func.count()).select_from(PetJourney).where(PetJourney.pet_id.in_(pet_ids))
    )
    accounts = list(
        (
            await session.scalars(
                select(WalletAccount).where(WalletAccount.household_id.in_(household_ids))
            )
        ).all()
    )
    wallet_balance = await session.scalar(
        select(func.coalesce(func.sum(WalletCredit.remaining_amount_irr), 0)).where(
            WalletCredit.wallet_account_id.in_([account.id for account in accounts]),
            WalletCredit.expires_at > utc_now(),
        )
    )
    return {
        "identity_id": identity_id,
        "households": [{"id": item.id, "name": item.name} for item in households],
        "pets": [{"id": item.id, "name": item.name, "species": item.species} for item in pets],
        "orders": [
            {
                "id": item.id,
                "status": item.status,
                "total_irr": item.merchandise_total_irr,
                "commitment_at": item.delivery_commitment_at,
            }
            for item in orders
        ],
        "counts": {
            "payments": payment_count or 0,
            "inventory_units": inventory_count or 0,
            "journeys": journey_count or 0,
        },
        "wallet_available_irr": int(wallet_balance or 0),
    }


def _activation_item(run: KnowledgeActivationRun) -> dict[str, object]:
    return {
        "id": run.id,
        "release_id": run.release_id,
        "previous_release_id": run.previous_release_id,
        "status": run.status,
        "preflight": run.preflight_report,
        "result": run.result_report,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "rolled_back_at": run.rolled_back_at,
        "failure_code": run.failure_code,
    }


def _audit(
    session: AsyncSession,
    request: Request,
    operator_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID,
    reason: str,
    after: dict[str, object],
) -> None:
    record_operator_action(
        session,
        operator_identity_id=operator_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        request_id=request_id_context.get(),
        reason=reason,
        before_facts=None,
        after_facts=after,
        source_ip=request.client.host if request.client else None,
    )


def _validate_template_fields(event_key: str, body: str) -> None:
    allowed: dict[str, set[str]] = {
        "wallet.late_delivery_credit_granted": {
            "order_id",
            "household_id",
            "amount_irr",
            "expires_at",
        },
        "orders.shelf_life_exception_proposed": {
            "order_id",
            "household_id",
            "shelf_life_exception_id",
            "order_line_id",
            "respond_by",
        },
        "reservations.proposed": {
            "reservation_id",
            "household_id",
            "reconfirmed_price_irr",
            "customer_respond_by",
        },
    }
    if event_key not in allowed:
        raise HTTPException(status_code=422, detail="unsupported_notification_event")
    try:
        fields = {field for _, field, _, _ in Formatter().parse(body) if field}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid_template_format") from exc
    if not fields.issubset(allowed[event_key]):
        raise HTTPException(status_code=422, detail="unsupported_template_placeholder")


def _safe_filename(value: str) -> str:
    basename = Path(value).name
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", basename).strip("._")
    if not safe:
        raise HTTPException(status_code=422, detail="invalid_evidence_filename")
    return safe[:200]
