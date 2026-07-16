from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class HealthMeasurement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_health_measurements"
    __table_args__ = (
        CheckConstraint(
            "measurement_type IN "
            "('weight','height_at_withers','chest_circumference','body_length',"
            "'temperature','resting_respiratory_rate')",
            name="valid_measurement_type",
        ),
        CheckConstraint("value > 0", name="positive_value"),
        CheckConstraint(
            "source IN ('owner_reported','veterinarian_reported','device_import')",
            name="valid_source",
        ),
        CheckConstraint("confidence IN ('low','medium','high')", name="valid_confidence"),
        CheckConstraint("status IN ('active','corrected','voided')", name="valid_status"),
    )

    pet_id: Mapped[UUID] = mapped_column(
        ForeignKey("pets_pets.id", ondelete="CASCADE"), index=True
    )
    measurement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    measurement_method: Mapped[str | None] = mapped_column(String(100))
    entered_by_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True
    )
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    supersedes_measurement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pet_health_measurements.id"), unique=True
    )
    correction_reason: Mapped[str | None] = mapped_column(Text)


class BenchmarkDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_health_benchmark_definitions"
    __table_args__ = (
        UniqueConstraint("claim_id", name="one_definition_per_claim"),
        CheckConstraint(
            "measurement_type IN ('weight','height_at_withers')", name="valid_measurement_type"
        ),
        CheckConstraint("unit IN ('kg','cm')", name="valid_unit"),
        CheckConstraint(
            "(measurement_type = 'weight' AND unit = 'kg') OR "
            "(measurement_type = 'height_at_withers' AND unit = 'cm')",
            name="measurement_unit_match",
        ),
        CheckConstraint(
            "reference_purpose IN ('registry_conformation','population_reference',"
            "'growth_reference')",
            name="valid_reference_purpose",
        ),
        CheckConstraint(
            "minimum_value >= 0 AND maximum_value >= minimum_value", name="valid_range"
        ),
        CheckConstraint(
            "minimum_age_days IS NULL OR maximum_age_days IS NULL OR "
            "maximum_age_days >= minimum_age_days",
            name="valid_age_range",
        ),
        CheckConstraint(
            "sex_scope IN ('combined','female','male')", name="valid_sex_scope"
        ),
        CheckConstraint(
            "neuter_scope IN ('any','intact','neutered')", name="valid_neuter_scope"
        ),
        CheckConstraint("status IN ('active','withdrawn')", name="valid_status"),
    )

    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_releases.id", ondelete="CASCADE"), index=True
    )
    claim_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_claims.id", ondelete="CASCADE"), index=True
    )
    breed_external_id: Mapped[str] = mapped_column(String(150), index=True)
    variety_external_id: Mapped[str | None] = mapped_column(String(150))
    measurement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    minimum_value: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    maximum_value: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    minimum_age_days: Mapped[int | None] = mapped_column(Integer)
    maximum_age_days: Mapped[int | None] = mapped_column(Integer)
    life_stage: Mapped[str | None] = mapped_column(String(40))
    sex_scope: Mapped[str] = mapped_column(String(20), nullable=False)
    neuter_scope: Mapped[str] = mapped_column(String(20), nullable=False)
    population_geography: Mapped[str] = mapped_column(String(200), nullable=False)
    measurement_definition_fa: Mapped[str] = mapped_column(Text, nullable=False)
    comparison_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    recorded_by_operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True
    )


class MeasurementReminder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_health_measurement_reminders"
    __table_args__ = (
        CheckConstraint(
            "measurement_type IN ('weight','body_condition')", name="valid_measurement_type"
        ),
        CheckConstraint(
            "status IN ('scheduled','completed','dismissed')", name="valid_status"
        ),
    )

    pet_id: Mapped[UUID] = mapped_column(
        ForeignKey("pets_pets.id", ondelete="CASCADE"), index=True
    )
    measurement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)
    created_by_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PetConsent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_health_consents"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('body_photographs','medical_records')", name="valid_purpose"
        ),
        CheckConstraint("status IN ('granted','withdrawn')", name="valid_status"),
        Index(
            "uq_pet_health_consents_active_purpose",
            "pet_id",
            "purpose",
            unique=True,
            postgresql_where=text("status = 'granted'"),
        ),
    )

    pet_id: Mapped[UUID] = mapped_column(
        ForeignKey("pets_pets.id", ondelete="CASCADE"), index=True
    )
    granted_by_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="granted", nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PetAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_health_assets"
    __table_args__ = (
        CheckConstraint(
            "category IN ('body_top','body_side','medical_document','lab_result','other_medical')",
            name="valid_category",
        ),
        CheckConstraint(
            "purpose IN ('body_photographs','medical_records')", name="valid_purpose"
        ),
        CheckConstraint("status IN ('active','removed')", name="valid_status"),
    )

    pet_id: Mapped[UUID] = mapped_column(
        ForeignKey("pets_pets.id", ondelete="CASCADE"), index=True
    )
    consent_id: Mapped[UUID] = mapped_column(ForeignKey("pet_health_consents.id"), index=True)
    uploaded_by_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BodyAssessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_health_body_assessments"
    __table_args__ = (
        CheckConstraint("bcs_score >= 1 AND bcs_score <= 9", name="valid_bcs_score"),
        CheckConstraint("bcs_scale = 9", name="valid_bcs_scale"),
        CheckConstraint(
            "muscle_condition IN ('normal','mild_loss','moderate_loss','severe_loss','unknown')",
            name="valid_muscle_condition",
        ),
        CheckConstraint(
            "assessment_source IN ('owner_reported','veterinarian_confirmed')",
            name="valid_assessment_source",
        ),
        CheckConstraint("status IN ('active','superseded','voided')", name="valid_status"),
    )

    pet_id: Mapped[UUID] = mapped_column(
        ForeignKey("pets_pets.id", ondelete="CASCADE"), index=True
    )
    bcs_score: Mapped[int] = mapped_column(Integer, nullable=False)
    bcs_scale: Mapped[int] = mapped_column(Integer, default=9, nullable=False)
    muscle_condition: Mapped[str] = mapped_column(String(30), nullable=False)
    assessment_source: Mapped[str] = mapped_column(String(40), nullable=False)
    answers: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entered_by_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    veterinarian_name: Mapped[str | None] = mapped_column(String(200))
    veterinarian_credential: Mapped[str | None] = mapped_column(String(200))
    confirmed_by_operator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity_auth_identities.id")
    )
    veterinarian_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmation_evidence_file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("trust_evidence_files.id")
    )


class BodyAssessmentAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pet_health_body_assessment_assets"
    __table_args__ = (
        UniqueConstraint("assessment_id", "asset_id", name="assessment_asset"),
        CheckConstraint("role IN ('top','side','supporting')", name="valid_role"),
    )

    assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_health_body_assessments.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_health_assets.id", ondelete="RESTRICT"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
