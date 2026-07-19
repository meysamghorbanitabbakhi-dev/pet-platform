from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeRelease(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_knowledge_releases"
    __table_args__ = (
        CheckConstraint("language = 'fa-IR'", name="persian_only"),
        CheckConstraint(
            "status IN ('validated','imported','published','superseded','rejected','withdrawn',"
            "'review_expired')",
            name="valid_status",
        ),
        Index(
            "uq_pet_knowledge_one_published_release",
            "status",
            unique=True,
            postgresql_where=text("status = 'published'"),
        ),
    )

    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    imported_by_operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True
    )
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    breed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    variety_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_count: Mapped[int] = mapped_column(Integer, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_release_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pet_knowledge_releases.id")
    )


class KnowledgeBreed(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_knowledge_breeds"
    __table_args__ = (
        UniqueConstraint("release_id", "external_id", name="release_external_id"),
        CheckConstraint("species IN ('dog','cat')", name="valid_species"),
    )

    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_releases.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(150), nullable=False)
    species: Mapped[str] = mapped_column(String(10), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(300), nullable=False)
    name_en: Mapped[str] = mapped_column(String(300), nullable=False)
    record: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class KnowledgeVariety(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_knowledge_varieties"
    __table_args__ = (
        UniqueConstraint("release_id", "external_id", name="release_external_id"),
    )

    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_releases.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(150), nullable=False)
    breed_external_id: Mapped[str] = mapped_column(String(150), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(300), nullable=False)
    name_en: Mapped[str] = mapped_column(String(300), nullable=False)
    record: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class KnowledgeSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_knowledge_sources"
    __table_args__ = (
        UniqueConstraint("release_id", "external_id", name="release_external_id"),
    )

    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_releases.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    record: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class KnowledgeClaim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_knowledge_claims"
    __table_args__ = (
        UniqueConstraint("release_id", "external_id", name="release_external_id"),
        CheckConstraint(
            "review_status IN "
            "('draft','editorial_reviewed','veterinary_review_required','veterinary_approved',"
            "'rejected','superseded','withdrawn')",
            name="valid_review_status",
        ),
        CheckConstraint(
            "app_eligible = false OR review_status = 'veterinary_approved'",
            name="eligible_requires_veterinary_approval",
        ),
    )

    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_releases.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    breed_external_id: Mapped[str] = mapped_column(String(150), nullable=False)
    variety_external_id: Mapped[str | None] = mapped_column(String(150))
    claim_type: Mapped[str] = mapped_column(String(100), nullable=False)
    text_fa: Mapped[str] = mapped_column(String(5000), nullable=False)
    review_status: Mapped[str] = mapped_column(String(40), nullable=False)
    app_eligible: Mapped[bool] = mapped_column(default=False, nullable=False)
    record: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class KnowledgeClaimSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_knowledge_claim_sources"
    __table_args__ = (
        UniqueConstraint("claim_id", "source_id", name="claim_source"),
    )

    claim_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_claims.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_sources.id", ondelete="RESTRICT"), index=True
    )


class KnowledgeGuidance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_knowledge_guidance"
    __table_args__ = (
        UniqueConstraint("release_id", "external_id", name="release_external_id"),
        CheckConstraint(
            "review_status IN ('veterinary_review_required','veterinary_approved','rejected',"
            "'superseded','withdrawn')",
            name="valid_review_status",
        ),
        CheckConstraint(
            "app_eligible = false OR review_status = 'veterinary_approved'",
            name="eligible_requires_veterinary_approval",
        ),
    )

    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_releases.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    breed_external_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    variety_external_id: Mapped[str | None] = mapped_column(String(150))
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    text_fa: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_claim_external_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    review_status: Mapped[str] = mapped_column(String(40), nullable=False)
    app_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    record: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

class KnowledgeReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_knowledge_reviews"
    __table_args__ = (
        CheckConstraint("scope IN ('claim','guidance','release')", name="valid_scope"),
        CheckConstraint("decision IN ('approved','rejected')", name="valid_decision"),
        CheckConstraint(
            "reviewer_disclosure = 'anonymous_external_veterinarian'",
            name="anonymous_reviewer_only",
        ),
        CheckConstraint(
            "(scope = 'claim' AND claim_id IS NOT NULL AND guidance_id IS NULL) OR "
            "(scope = 'guidance' AND guidance_id IS NOT NULL AND claim_id IS NULL) OR "
            "(scope = 'release' AND claim_id IS NULL AND guidance_id IS NULL)",
            name="valid_scope_target",
        ),
    )

    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_releases.id", ondelete="CASCADE"), index=True
    )
    claim_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pet_knowledge_claims.id", ondelete="CASCADE"), index=True
    )
    guidance_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pet_knowledge_guidance.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewer_disclosure: Mapped[str] = mapped_column(String(50), nullable=False)
    reviewed_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_file_id: Mapped[UUID] = mapped_column(ForeignKey("trust_evidence_files.id"))
    recorded_by_operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    limitations_fa: Mapped[str | None] = mapped_column(Text)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credential_verified_privately: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )


class KnowledgeReviewTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_knowledge_review_tasks"
    __table_args__ = (
        UniqueConstraint("review_id", name="one_task_per_review"),
        CheckConstraint("status IN ('due','expired','resolved')", name="valid_status"),
    )

    review_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_reviews.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeActivationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_knowledge_activation_runs"
    __table_args__ = (
        UniqueConstraint("release_id", name="one_activation_per_release"),
        CheckConstraint(
            "status IN ('ready','blocked','running','completed','rolled_back','failed')",
            name="valid_status",
        ),
        CheckConstraint(
            "expected_guidance_count >= 0 AND expected_benchmark_candidate_count >= 0",
            name="nonnegative_expected_counts",
        ),
    )

    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_releases.id", ondelete="CASCADE"), index=True
    )
    previous_release_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pet_knowledge_releases.id"), index=True
    )
    evidence_file_id: Mapped[UUID] = mapped_column(ForeignKey("trust_evidence_files.id"))
    expected_release_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_guidance_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_benchmark_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    limitations_fa: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    preflight_report: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    result_report: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_by_operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))


class KnowledgeGuidancePreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_knowledge_guidance_preferences"
    __table_args__ = (
        UniqueConstraint("pet_id", "guidance_id", name="pet_guidance"),
        CheckConstraint("status IN ('dismissed','snoozed')", name="valid_status"),
        CheckConstraint(
            "(status = 'dismissed' AND snoozed_until IS NULL) OR "
            "(status = 'snoozed' AND snoozed_until IS NOT NULL)",
            name="valid_snooze_state",
        ),
    )

    pet_id: Mapped[UUID] = mapped_column(
        ForeignKey("pets_pets.id", ondelete="CASCADE"), index=True
    )
    guidance_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_guidance.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    acted_by_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True
    )
