from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.pet_health.models import BenchmarkDefinition
from app.modules.pet_knowledge.models import (
    KnowledgeActivationRun,
    KnowledgeClaim,
    KnowledgeGuidance,
    KnowledgeRelease,
    KnowledgeReview,
)
from app.modules.pet_knowledge.service import materialize_release_benchmarks
from app.modules.pet_knowledge.validation import canonical_bytes


async def build_activation_preflight(
    session: AsyncSession,
    *,
    release: KnowledgeRelease,
    expected_checksum: str,
    reviewed_at: datetime,
    next_review_at: datetime | None,
    expected_guidance_count: int,
    expected_benchmark_candidate_count: int,
) -> dict[str, object]:
    blockers: list[str] = []
    if release.status != "imported":
        blockers.append("release_not_imported")
    if release.checksum_sha256 != expected_checksum:
        blockers.append("release_checksum_mismatch")
    now = utc_now()
    if reviewed_at > now:
        blockers.append("review_in_future")
    if next_review_at is not None and next_review_at <= reviewed_at:
        blockers.append("invalid_next_review_at")
    claim_count = int(
        await session.scalar(
            select(func.count(KnowledgeClaim.id)).where(KnowledgeClaim.release_id == release.id)
        )
        or 0
    )
    guidance_count = int(
        await session.scalar(
            select(func.count(KnowledgeGuidance.id)).where(
                KnowledgeGuidance.release_id == release.id
            )
        )
        or 0
    )
    benchmark_candidates = int(
        await session.scalar(
            select(func.count(KnowledgeClaim.id)).where(
                KnowledgeClaim.release_id == release.id,
                KnowledgeClaim.claim_type.in_(("adult_weight_reference", "height_reference")),
            )
        )
        or 0
    )
    if claim_count != release.claim_count:
        blockers.append("stored_claim_count_mismatch")
    if claim_count == 0:
        blockers.append("release_has_no_claims")
    if guidance_count != expected_guidance_count:
        blockers.append("stored_guidance_count_mismatch")
    if benchmark_candidates != expected_benchmark_candidate_count:
        blockers.append("benchmark_candidate_count_mismatch")
    current = await session.scalar(
        select(KnowledgeRelease).where(KnowledgeRelease.status == "published").limit(1)
    )
    return {
        "ready": not blockers,
        "blockers": blockers,
        "release_status": release.status,
        "checksum_matches": release.checksum_sha256 == expected_checksum,
        "claims": claim_count,
        "guidance": guidance_count,
        "benchmark_candidates": benchmark_candidates,
        "previous_release_id": str(current.id) if current is not None else None,
    }


async def execute_activation(
    session: AsyncSession, *, run: KnowledgeActivationRun, operator_id: UUID
) -> dict[str, object]:
    release = await session.get(KnowledgeRelease, run.release_id, with_for_update=True)
    if release is None or release.status != "imported":
        raise ValueError("release_not_activatable")
    if release.checksum_sha256 != run.expected_release_checksum_sha256:
        raise ValueError("release_checksum_mismatch")
    now = utc_now()
    run.status = "running"
    run.started_at = now
    claims = list(
        (
            await session.scalars(
                select(KnowledgeClaim)
                .where(KnowledgeClaim.release_id == release.id)
                .with_for_update()
            )
        ).all()
    )
    guidance_rows = list(
        (
            await session.scalars(
                select(KnowledgeGuidance)
                .where(KnowledgeGuidance.release_id == release.id)
                .with_for_update()
            )
        ).all()
    )
    for claim in claims:
        claim.review_status = "veterinary_approved"
        claim.app_eligible = True
        session.add(_review(run, operator_id, claim=claim))
    for guidance in guidance_rows:
        guidance.review_status = "veterinary_approved"
        guidance.app_eligible = True
        session.add(_review(run, operator_id, guidance=guidance))
    current = await session.scalar(
        select(KnowledgeRelease)
        .where(KnowledgeRelease.status == "published")
        .with_for_update()
    )
    if current is not None:
        current.status = "superseded"
        run.previous_release_id = current.id
    release.status = "published"
    release.published_at = now
    release.supersedes_release_id = current.id if current is not None else None
    session.add(_review(run, operator_id))
    await session.flush()
    benchmark_result = await materialize_release_benchmarks(
        session, release=release, operator_id=operator_id
    )
    result: dict[str, object] = {
        "approved_claims": len(claims),
        "approved_guidance": len(guidance_rows),
        "benchmarks": benchmark_result,
        "published_release_id": str(release.id),
        "previous_release_id": str(current.id) if current is not None else None,
    }
    run.status = "completed"
    run.completed_at = utc_now()
    run.result_report = result
    return result


async def rollback_activation(
    session: AsyncSession, *, run: KnowledgeActivationRun
) -> dict[str, object]:
    if run.status != "completed":
        raise ValueError("activation_not_rollbackable")
    release = await session.get(KnowledgeRelease, run.release_id, with_for_update=True)
    if release is None or release.status != "published":
        raise ValueError("activated_release_not_current")
    previous: KnowledgeRelease | None = None
    if run.previous_release_id is not None:
        previous = await session.get(
            KnowledgeRelease, run.previous_release_id, with_for_update=True
        )
        if previous is None or previous.status != "superseded":
            raise ValueError("previous_release_not_restorable")
        valid_review = await session.scalar(
            select(KnowledgeReview.id)
            .where(
                KnowledgeReview.release_id == previous.id,
                KnowledgeReview.scope == "release",
                KnowledgeReview.decision == "approved",
                KnowledgeReview.expired_at.is_(None),
                or_(
                    KnowledgeReview.next_review_at.is_(None),
                    KnowledgeReview.next_review_at > utc_now(),
                ),
            )
            .order_by(KnowledgeReview.reviewed_at.desc())
            .limit(1)
        )
        if valid_review is None:
            raise ValueError("previous_release_review_not_current")
    release.status = "withdrawn"
    release.withdrawn_at = utc_now()
    await session.flush()
    if previous is not None:
        previous.status = "published"
    await session.execute(
        update(KnowledgeClaim)
        .where(KnowledgeClaim.release_id == release.id)
        .values(review_status="withdrawn", app_eligible=False)
    )
    await session.execute(
        update(KnowledgeGuidance)
        .where(KnowledgeGuidance.release_id == release.id)
        .values(review_status="withdrawn", app_eligible=False)
    )
    await session.execute(
        update(BenchmarkDefinition)
        .where(BenchmarkDefinition.release_id == release.id)
        .values(status="withdrawn")
    )
    run.status = "rolled_back"
    run.rolled_back_at = utc_now()
    return {
        "withdrawn_release_id": str(release.id),
        "restored_release_id": str(previous.id) if previous is not None else None,
    }


def _review(
    run: KnowledgeActivationRun,
    operator_id: UUID,
    *,
    claim: KnowledgeClaim | None = None,
    guidance: KnowledgeGuidance | None = None,
) -> KnowledgeReview:
    target = (
        claim.record
        if claim is not None
        else guidance.record if guidance is not None else None
    )
    checksum = (
        hashlib.sha256(canonical_bytes(target)).hexdigest()
        if target is not None
        else run.expected_release_checksum_sha256
    )
    scope = "claim" if claim is not None else "guidance" if guidance is not None else "release"
    return KnowledgeReview(
        release_id=run.release_id,
        claim_id=claim.id if claim is not None else None,
        guidance_id=guidance.id if guidance is not None else None,
        scope=scope,
        decision="approved",
        reviewer_disclosure="anonymous_external_veterinarian",
        reviewed_checksum_sha256=checksum,
        evidence_file_id=run.evidence_file_id,
        recorded_by_operator_id=operator_id,
        reviewed_at=run.reviewed_at,
        next_review_at=run.next_review_at,
        limitations_fa=run.limitations_fa,
        credential_verified_privately=True,
    )
