from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Pet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pets_pets"
    __table_args__ = (
        CheckConstraint("species IN ('dog','cat')", name="valid_species"),
        CheckConstraint("status IN ('active','archived')", name="valid_status"),
        CheckConstraint(
            "birth_date_precision IS NULL OR birth_date_precision IN "
            "('exact','month','year','estimated')",
            name="valid_birth_date_precision",
        ),
        CheckConstraint("sex IS NULL OR sex IN ('female','male','unknown')", name="valid_sex"),
        CheckConstraint(
            "neuter_status IS NULL OR neuter_status IN ('intact','neutered','unknown')",
            name="valid_neuter_status",
        ),
        CheckConstraint(
            "expected_adult_size IS NULL OR expected_adult_size IN "
            "('very_small','small','medium','large','giant','unknown')",
            name="valid_expected_adult_size",
        ),
        CheckConstraint(
            "breed_identification_source IS NULL OR breed_identification_source IN "
            "('owner_reported','veterinarian_reported','registry_confirmed','dna_estimated','unknown')",
            name="valid_breed_identification_source",
        ),
        CheckConstraint(
            "reproductive_state IS NULL OR reproductive_state IN "
            "('not_applicable','pregnant','lactating','unknown')",
            name="valid_reproductive_state",
        ),
        CheckConstraint(
            "breed_selection_mode IS NULL OR breed_selection_mode IN ('known','mixed','unknown')",
            name="valid_breed_selection_mode",
        ),
    )

    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("households_households.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    species: Mapped[str] = mapped_column(String(20), nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date)
    birth_date_precision: Mapped[str | None] = mapped_column(String(20))
    sex: Mapped[str | None] = mapped_column(String(20))
    neuter_status: Mapped[str | None] = mapped_column(String(20))
    expected_adult_size: Mapped[str | None] = mapped_column(String(20))
    breed_reference_id: Mapped[str | None] = mapped_column(String(150), index=True)
    breed_variety_id: Mapped[str | None] = mapped_column(String(150))
    breed_identification_source: Mapped[str | None] = mapped_column(String(40))
    mixed_breed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    breed_selection_mode: Mapped[str | None] = mapped_column(String(20))
    reproductive_state: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class PetBreedSelection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pets_breed_selections"
    __table_args__ = (
        CheckConstraint("selection_mode IN ('known','mixed','unknown')", name="valid_mode"),
        CheckConstraint(
            "identification_source IN ('owner_reported','veterinarian_reported',"
            "'registry_confirmed','dna_estimated','unknown')",
            name="valid_identification_source",
        ),
        CheckConstraint(
            "(selection_mode = 'known' AND breed_reference_id IS NOT NULL) OR "
            "(selection_mode IN ('mixed','unknown') AND breed_reference_id IS NULL)",
            name="valid_selection_target",
        ),
    )

    pet_id: Mapped[UUID] = mapped_column(
        ForeignKey("pets_pets.id", ondelete="CASCADE"), index=True
    )
    knowledge_release_id: Mapped[UUID] = mapped_column(
        ForeignKey("pet_knowledge_releases.id"), index=True
    )
    selection_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    breed_reference_id: Mapped[str | None] = mapped_column(String(150))
    breed_variety_id: Mapped[str | None] = mapped_column(String(150))
    identification_source: Mapped[str] = mapped_column(String(40), nullable=False)
    selected_by_identity_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), index=True
    )
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
