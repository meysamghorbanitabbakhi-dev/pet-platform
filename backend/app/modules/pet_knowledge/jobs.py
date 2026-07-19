from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.time import utc_now
from app.modules.pet_knowledge.models import (
    KnowledgeClaim,
    KnowledgeGuidance,
    KnowledgeRelease,
    KnowledgeReview,
    KnowledgeReviewTask,
)


async def process_knowledge_review_lifecycle(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    reminder_days: int = 14,
    batch_size: int = 100,
) -> dict[str, int]:
    """Create operator tasks and fail closed when the latest approval expires."""
    now = utc_now()
    reminder_cutoff = now + timedelta(days=reminder_days)
    counts = {"tasks_created": 0, "expired": 0, "resolved": 0}
    async with session_factory() as session:
        reviews = list(
            (
                await session.scalars(
                    select(KnowledgeReview)
                    .where(
                        KnowledgeReview.decision == "approved",
                        KnowledgeReview.next_review_at.is_not(None),
                        KnowledgeReview.next_review_at <= reminder_cutoff,
                    )
                    .order_by(KnowledgeReview.next_review_at)
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for review in reviews:
            due_at = review.next_review_at
            if due_at is None:
                continue
            later_filters = [
                KnowledgeReview.scope == review.scope,
                KnowledgeReview.release_id == review.release_id,
                KnowledgeReview.decision == "approved",
                KnowledgeReview.reviewed_at > review.reviewed_at,
            ]
            if review.scope == "claim":
                later_filters.append(KnowledgeReview.claim_id == review.claim_id)
                later_filters.append(KnowledgeReview.guidance_id.is_(None))
            elif review.scope == "guidance":
                later_filters.append(KnowledgeReview.guidance_id == review.guidance_id)
                later_filters.append(KnowledgeReview.claim_id.is_(None))
            else:
                later_filters.append(KnowledgeReview.claim_id.is_(None))
                later_filters.append(KnowledgeReview.guidance_id.is_(None))
            superseding = await session.scalar(
                select(KnowledgeReview.id).where(*later_filters).limit(1)
            )
            task = await session.scalar(
                select(KnowledgeReviewTask).where(KnowledgeReviewTask.review_id == review.id)
            )
            if superseding is not None:
                if task is not None and task.status != "resolved":
                    task.status = "resolved"
                    task.resolved_at = now
                    counts["resolved"] += 1
                continue
            if task is None:
                task = KnowledgeReviewTask(
                    review_id=review.id,
                    status="due",
                    due_at=due_at,
                    detected_at=now,
                )
                session.add(task)
                counts["tasks_created"] += 1
            if due_at > now or review.expired_at is not None:
                continue
            review.expired_at = now
            task.status = "expired"
            counts["expired"] += 1
            if review.scope == "claim" and review.claim_id is not None:
                claim = await session.get(KnowledgeClaim, review.claim_id, with_for_update=True)
                if claim is not None and claim.review_status == "veterinary_approved":
                    claim.review_status = "veterinary_review_required"
                    claim.app_eligible = False
            elif review.scope == "guidance" and review.guidance_id is not None:
                guidance = await session.get(
                    KnowledgeGuidance, review.guidance_id, with_for_update=True
                )
                if guidance is not None and guidance.review_status == "veterinary_approved":
                    guidance.review_status = "veterinary_review_required"
                    guidance.app_eligible = False
            elif review.scope == "release":
                release = await session.get(
                    KnowledgeRelease, review.release_id, with_for_update=True
                )
                if release is not None and release.status == "published":
                    release.status = "review_expired"
        await session.commit()
    return counts
