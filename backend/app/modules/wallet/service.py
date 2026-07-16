from __future__ import annotations

import calendar
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.modules.orders.models import Order
from app.modules.system.outbox import DomainEvent, add_outbox_event
from app.modules.wallet.models import (
    WalletAccount,
    WalletCredit,
    WalletDebit,
    WalletDebitAllocation,
)


class WalletError(Exception):
    pass


async def grant_late_delivery_credit(
    session: AsyncSession,
    *,
    order_id: UUID,
    basis_points: int = 500,
    expiry_months: int = 3,
) -> WalletCredit:
    order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None or order.paid_at is None or order.delivery_commitment_at is None:
        raise WalletError("order has no paid delivery commitment")
    effective_delivery = order.delivered_at or utc_now()
    if effective_delivery <= order.delivery_commitment_at:
        raise WalletError("order is not late")
    account = await session.scalar(
        select(WalletAccount).where(WalletAccount.household_id == order.household_id)
    )
    if account is None:
        account = WalletAccount(household_id=order.household_id)
        session.add(account)
        await session.flush()
    existing = await session.scalar(
        select(WalletCredit).where(
            WalletCredit.source_type == "late_delivery",
            WalletCredit.source_id == str(order.id),
        )
    )
    if existing is not None:
        return existing
    amount = (order.merchandise_total_irr * basis_points) // 10_000
    if amount <= 0:
        raise WalletError("calculated credit is zero")
    now = utc_now()
    credit = WalletCredit(
        wallet_account_id=account.id,
        original_amount_irr=amount,
        remaining_amount_irr=amount,
        expires_at=_add_months(now, expiry_months),
        source_type="late_delivery",
        source_id=str(order.id),
    )
    session.add(credit)
    await session.flush()
    add_outbox_event(
        session,
        DomainEvent(
            event_type="wallet.late_delivery_credit_granted",
            aggregate_type="wallet_credit",
            aggregate_id=str(credit.id),
            payload={
                "order_id": str(order.id),
                "household_id": str(order.household_id),
                "amount_irr": amount,
                "expires_at": credit.expires_at.isoformat(),
            },
        ),
    )
    return credit


async def debit_wallet(
    session: AsyncSession,
    *,
    wallet_account_id: UUID,
    amount_irr: int,
    idempotency_key: str,
) -> WalletDebit:
    if amount_irr <= 0:
        raise WalletError("debit amount must be positive")
    existing = await session.scalar(
        select(WalletDebit).where(WalletDebit.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing
    now = utc_now()
    credits = list(
        (
            await session.scalars(
                select(WalletCredit)
                .where(
                    WalletCredit.wallet_account_id == wallet_account_id,
                    WalletCredit.remaining_amount_irr > 0,
                    WalletCredit.expires_at > now,
                )
                .order_by(WalletCredit.expires_at, WalletCredit.created_at)
                .with_for_update()
            )
        ).all()
    )
    if sum(credit.remaining_amount_irr for credit in credits) < amount_irr:
        raise WalletError("insufficient wallet balance")
    debit = WalletDebit(
        wallet_account_id=wallet_account_id,
        amount_irr=amount_irr,
        idempotency_key=idempotency_key,
    )
    session.add(debit)
    await session.flush()
    remaining = amount_irr
    for credit in credits:
        allocated = min(remaining, credit.remaining_amount_irr)
        if allocated:
            credit.remaining_amount_irr -= allocated
            session.add(
                WalletDebitAllocation(
                    wallet_debit_id=debit.id,
                    wallet_credit_id=credit.id,
                    amount_irr=allocated,
                )
            )
            remaining -= allocated
        if remaining == 0:
            break
    await session.commit()
    return debit


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)
