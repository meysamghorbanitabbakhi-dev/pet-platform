from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EvidenceFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trust_evidence_files"

    storage_key: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by_operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity_auth_identities.id"), nullable=False
    )
