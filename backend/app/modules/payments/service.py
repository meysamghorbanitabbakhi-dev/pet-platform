from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.integrations.payment.port import PaymentGateway, PaymentRequest
from app.modules.orders.models import Order
from app.modules.payments.models import PaymentAttempt
from app.modules.sourcing.models import SourcingJob
from app.modules.system.outbox import DomainEvent, add_outbox_event


class PaymentWorkflowError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PaymentRedirect:
    attempt_id: UUID
    redirect_url: str


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    state: str
    order_id: UUID


class PaymentService:
    def __init__(self, *, delivery_commitment_hours: int = 366) -> None:
        if not 1 <= delivery_commitment_hours <= 720:
            raise ValueError("delivery commitment must be between 1 and 720 hours")
        self._delivery_commitment_hours = delivery_commitment_hours

    async def initiate(
        self,
        session: AsyncSession,
        gateway: PaymentGateway,
        *,
        order_id: UUID,
        customer_identity_id: UUID,
        customer_mobile_e164: str,
        callback_url: str,
        idempotency_key: str,
    ) -> PaymentRedirect:
        order = await session.get(Order, order_id)
        if (
            order is None
            or order.customer_identity_id != customer_identity_id
            or order.status != "awaiting_payment"
        ):
            raise PaymentWorkflowError("order is not awaiting payment")
        existing = await session.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == order.id,
                PaymentAttempt.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.status != "redirect_ready" or existing.redirect_url is None:
                raise PaymentWorkflowError("payment request is already processing")
            return PaymentRedirect(existing.id, existing.redirect_url)

        attempt = PaymentAttempt(
            order_id=order.id,
            provider="zarinpal",
            status="created",
            amount_irr=order.merchandise_total_irr,
            currency="IRR",
            idempotency_key=idempotency_key,
        )
        session.add(attempt)
        await session.flush()
        initiation = await gateway.initiate(
            PaymentRequest(
                amount_irr=attempt.amount_irr,
                callback_url=callback_url,
                description=f"Payment for order {order.id}",
                order_id=str(order.id),
                mobile_e164=customer_mobile_e164,
            )
        )
        attempt.provider_reference = initiation.provider_reference
        attempt.redirect_url = initiation.redirect_url
        attempt.status = "redirect_ready"
        await session.commit()
        return PaymentRedirect(attempt.id, initiation.redirect_url)

    async def verify(
        self,
        session: AsyncSession,
        gateway: PaymentGateway,
        *,
        provider_reference: str,
    ) -> Order:
        attempt = await session.scalar(
            select(PaymentAttempt)
            .where(PaymentAttempt.provider_reference == provider_reference)
            .with_for_update()
        )
        if attempt is None:
            raise PaymentWorkflowError("unknown payment authority")
        order = await session.scalar(
            select(Order).where(Order.id == attempt.order_id).with_for_update()
        )
        if order is None:
            raise PaymentWorkflowError("payment order does not exist")
        if attempt.status == "verified":
            return order
        if attempt.amount_irr != order.merchandise_total_irr or attempt.currency != "IRR":
            raise PaymentWorkflowError("payment amount snapshot mismatch")

        verification = await gateway.verify(
            provider_reference=provider_reference,
            amount_irr=attempt.amount_irr,
        )
        now = utc_now()
        attempt.status = "verified"
        attempt.provider_transaction_id = verification.provider_transaction_id
        attempt.masked_card = verification.masked_card
        attempt.card_hash = verification.card_hash
        attempt.fee_irr = verification.fee_irr
        attempt.verified_at = now

        if order.paid_at is None:
            order.status = "paid"
            order.paid_at = now
            order.delivery_commitment_at = now + timedelta(hours=self._delivery_commitment_hours)
            session.add(SourcingJob(order_id=order.id, status="pending"))
            add_outbox_event(
                session,
                DomainEvent(
                    event_type="order.payment_verified",
                    aggregate_type="order",
                    aggregate_id=str(order.id),
                    payload={
                        "order_id": str(order.id),
                        "payment_attempt_id": str(attempt.id),
                        "paid_at": now.isoformat(),
                        "delivery_commitment_at": order.delivery_commitment_at.isoformat(),
                    },
                ),
            )
        await session.commit()
        return order

    async def reconcile(
        self,
        session: AsyncSession,
        gateway: PaymentGateway,
        *,
        attempt_id: UUID,
    ) -> ReconciliationResult:
        attempt = await session.scalar(
            select(PaymentAttempt).where(PaymentAttempt.id == attempt_id).with_for_update()
        )
        if attempt is None or attempt.provider_reference is None:
            raise PaymentWorkflowError("payment attempt is not reconcilable")
        if attempt.status == "verified":
            return ReconciliationResult("verified", attempt.order_id)
        inquiry = await gateway.inquiry(provider_reference=attempt.provider_reference)
        if inquiry.state in ("verified", "paid_unverified"):
            order = await self.verify(
                session, gateway, provider_reference=attempt.provider_reference
            )
            return ReconciliationResult("verified", order.id)
        if inquiry.state in ("failed", "reversed"):
            attempt.status = "failed"
            attempt.failure_code = inquiry.state
            await session.commit()
        return ReconciliationResult(inquiry.state, attempt.order_id)
