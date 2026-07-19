from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WalletAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wallet_accounts"

    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("households_households.id", ondelete="CASCADE"), unique=True
    )


class WalletCredit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wallet_credits"
    __table_args__ = (
        CheckConstraint("original_amount_irr > 0", name="positive_original_amount"),
        CheckConstraint("remaining_amount_irr >= 0", name="nonnegative_remaining_amount"),
        CheckConstraint(
            "remaining_amount_irr <= original_amount_irr", name="remaining_within_original"
        ),
        UniqueConstraint("source_type", "source_id", name="source_once"),
    )

    wallet_account_id: Mapped[UUID] = mapped_column(ForeignKey("wallet_accounts.id"), index=True)
    original_amount_irr: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_amount_irr: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)


class WalletDebit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wallet_debits"
    __table_args__ = (CheckConstraint("amount_irr > 0", name="positive_amount"),)

    wallet_account_id: Mapped[UUID] = mapped_column(ForeignKey("wallet_accounts.id"), index=True)
    amount_irr: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)


class WalletDebitAllocation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "wallet_debit_allocations"
    __table_args__ = (
        CheckConstraint("amount_irr > 0", name="positive_amount"),
        UniqueConstraint("wallet_debit_id", "wallet_credit_id", name="debit_credit"),
    )

    wallet_debit_id: Mapped[UUID] = mapped_column(
        ForeignKey("wallet_debits.id", ondelete="CASCADE"), index=True
    )
    wallet_credit_id: Mapped[UUID] = mapped_column(ForeignKey("wallet_credits.id"), index=True)
    amount_irr: Mapped[int] = mapped_column(Integer, nullable=False)
