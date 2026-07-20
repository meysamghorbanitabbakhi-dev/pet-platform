"""KPI computation (Workstream 6).

Each function computes exactly one KPI defined in kpi.KPI_REGISTRY
against a caller-supplied [window_start, window_end) UTC range. These
run as read-only queries in a reporting module, not overloaded onto
any transactional endpoint.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Offer
from app.modules.concierge.models import ConciergeOffer
from app.modules.food_estimation.models import FoodEstimate
from app.modules.inventory.models import InventoryUnit
from app.modules.journeys.models import PetJourney
from app.modules.orders.models import Order, OrderLine
from app.modules.payments.models import PaymentAttempt
from app.modules.pet_knowledge.models import KnowledgeGuidance, KnowledgeRelease
from app.modules.pets.models import Pet
from app.modules.price_intelligence.models import ExternalProductMatch
from app.modules.replenishment.models import ReplenishmentReservation
from app.modules.reporting.kpi import KPI_REGISTRY
from app.modules.sourcing.models import SourcingJob
from app.modules.wallet.models import WalletCredit, WalletDebit, WalletDebitAllocation


@dataclass(frozen=True, slots=True)
class KPIResult:
    key: str
    computable: bool
    numerator: float | None
    denominator: float | None
    value: float | None
    unit: str
    data_limitation: str | None = None


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


async def _conversion(session: AsyncSession, start: datetime, end: datetime) -> KPIResult:
    row = (
        await session.execute(
            select(
                func.count().filter(Order.paid_at.is_not(None)),
                func.count(),
            ).where(Order.created_at >= start, Order.created_at < end)
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "conversion", True, numerator, denominator, _ratio(numerator, denominator), "ratio"
    )


async def _payment_success(session: AsyncSession, start: datetime, end: datetime) -> KPIResult:
    row = (
        await session.execute(
            select(
                func.count().filter(PaymentAttempt.status == "verified"),
                func.count(),
            ).where(PaymentAttempt.created_at >= start, PaymentAttempt.created_at < end)
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "payment_success", True, numerator, denominator, _ratio(numerator, denominator), "ratio"
    )


async def _sourcing_failure(session: AsyncSession, start: datetime, end: datetime) -> KPIResult:
    row = (
        await session.execute(
            select(
                func.count().filter(SourcingJob.status == "failed"),
                func.count(),
            ).where(SourcingJob.created_at >= start, SourcingJob.created_at < end)
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "sourcing_failure", True, numerator, denominator, _ratio(numerator, denominator), "ratio"
    )


async def _delivery_within_commitment(
    session: AsyncSession, start: datetime, end: datetime
) -> KPIResult:
    row = (
        await session.execute(
            select(
                func.count().filter(Order.delivered_at <= Order.delivery_commitment_at),
                func.count(),
            ).where(Order.delivered_at >= start, Order.delivered_at < end)
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "delivery_within_commitment",
        True,
        numerator,
        denominator,
        _ratio(numerator, denominator),
        "ratio",
    )


async def _late_credit_issuance(
    session: AsyncSession, start: datetime, end: datetime
) -> KPIResult:
    row = (
        await session.execute(
            select(
                func.count(), func.coalesce(func.sum(WalletCredit.original_amount_irr), 0)
            ).where(
                WalletCredit.source_type == "late_delivery_credit",
                WalletCredit.created_at >= start,
                WalletCredit.created_at < end,
            )
        )
    ).one()
    denominator, numerator = row
    return KPIResult(
        "late_credit_issuance", True, float(numerator), float(denominator), None, "irr_total"
    )


async def _late_credit_redemption(
    session: AsyncSession, start: datetime, end: datetime
) -> KPIResult:
    numerator = (
        await session.execute(
            select(func.coalesce(func.sum(WalletDebitAllocation.amount_irr), 0))
            .select_from(WalletDebitAllocation)
            .join(WalletCredit, WalletCredit.id == WalletDebitAllocation.wallet_credit_id)
            .join(WalletDebit, WalletDebit.id == WalletDebitAllocation.wallet_debit_id)
            .where(
                WalletCredit.source_type == "late_delivery_credit",
                WalletDebit.created_at >= start,
                WalletDebit.created_at < end,
            )
        )
    ).scalar_one()
    denominator = (
        await session.execute(
            select(func.coalesce(func.sum(WalletCredit.original_amount_irr), 0)).where(
                WalletCredit.source_type == "late_delivery_credit",
                WalletCredit.created_at >= start,
                WalletCredit.created_at < end,
            )
        )
    ).scalar_one()
    return KPIResult(
        "late_credit_redemption",
        True,
        float(numerator),
        float(denominator),
        _ratio(float(numerator), float(denominator)),
        "ratio",
    )


async def _repeat_purchase(session: AsyncSession, start: datetime, end: datetime) -> KPIResult:
    # Per customer, their earliest paid order within the window -- "repeat"
    # means an even earlier paid order (possibly outside the window) exists
    # for that same customer.
    first_in_window = (
        select(
            Order.customer_identity_id.label("customer_identity_id"),
            func.min(Order.paid_at).label("first_paid_at"),
        )
        .where(Order.paid_at >= start, Order.paid_at < end)
        .group_by(Order.customer_identity_id)
        .subquery()
    )
    earlier_exists = (
        select(literal(1))
        .select_from(Order)
        .where(
            Order.customer_identity_id == first_in_window.c.customer_identity_id,
            Order.paid_at.is_not(None),
            Order.paid_at < first_in_window.c.first_paid_at,
        )
        .correlate(first_in_window)
        .exists()
    )
    row = (
        await session.execute(
            select(func.count().filter(earlier_exists), func.count()).select_from(
                first_in_window
            )
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "repeat_purchase", True, numerator, denominator, _ratio(numerator, denominator), "ratio"
    )


async def _gmv(session: AsyncSession, start: datetime, end: datetime) -> KPIResult:
    row = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(Order.merchandise_total_irr), 0)).where(
                Order.paid_at >= start, Order.paid_at < end
            )
        )
    ).one()
    denominator, numerator = row
    return KPIResult("gmv", True, float(numerator), float(denominator), None, "irr_total")


async def _margin(session: AsyncSession, start: datetime, end: datetime) -> KPIResult:
    definition = KPI_REGISTRY["margin"]
    return KPIResult(
        "margin", False, None, None, None, "irr_total", data_limitation=definition.data_limitation
    )


async def _reference_price_savings(
    session: AsyncSession, start: datetime, end: datetime
) -> KPIResult:
    savings = (OrderLine.unit_price_irr * -1 + Offer.reference_price_irr) * OrderLine.quantity
    reference_total = Offer.reference_price_irr * OrderLine.quantity
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(savings), 0),
                func.coalesce(func.sum(reference_total), 0),
            )
            .select_from(OrderLine)
            .join(Order, Order.id == OrderLine.order_id)
            .join(Offer, Offer.id == OrderLine.offer_id)
            .where(
                Order.paid_at >= start,
                Order.paid_at < end,
                Offer.reference_price_irr.is_not(None),
            )
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "reference_price_savings",
        True,
        float(numerator),
        float(denominator),
        _ratio(float(numerator), float(denominator)),
        "ratio",
    )


async def _reorder_recommendation_coverage(
    session: AsyncSession, start: datetime, end: datetime
) -> KPIResult:
    has_reservation = (
        select(literal(1))
        .where(ReplenishmentReservation.inventory_unit_id == InventoryUnit.id)
        .exists()
    )
    row = (
        await session.execute(
            select(func.count().filter(has_reservation), func.count()).where(
                InventoryUnit.state == "opened",
                InventoryUnit.opened_at >= start,
                InventoryUnit.opened_at < end,
            )
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "reorder_recommendation_coverage",
        True,
        numerator,
        denominator,
        _ratio(numerator, denominator),
        "ratio",
    )


async def _reorder_approval_rate(
    session: AsyncSession, start: datetime, end: datetime
) -> KPIResult:
    row = (
        await session.execute(
            select(
                func.count().filter(ReplenishmentReservation.status == "approved"),
                func.count(),
            ).where(
                ReplenishmentReservation.status.in_(
                    ("approved", "declined", "expired", "invalidated")
                ),
                ReplenishmentReservation.created_at >= start,
                ReplenishmentReservation.created_at < end,
            )
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "reorder_approval_rate",
        True,
        numerator,
        denominator,
        _ratio(numerator, denominator),
        "ratio",
    )


async def _replenishment_conversion(
    session: AsyncSession, start: datetime, end: datetime
) -> KPIResult:
    row = (
        await session.execute(
            select(
                func.count().filter(Order.status == "delivered"),
                func.count(),
            )
            .select_from(ReplenishmentReservation)
            .outerjoin(Order, Order.id == ReplenishmentReservation.resulting_order_id)
            .where(
                ReplenishmentReservation.status == "approved",
                ReplenishmentReservation.approved_at >= start,
                ReplenishmentReservation.approved_at < end,
            )
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "replenishment_conversion",
        True,
        numerator,
        denominator,
        _ratio(numerator, denominator),
        "ratio",
    )


async def _concierge_conversion(session: AsyncSession, start: datetime, end: datetime) -> KPIResult:
    row = (
        await session.execute(
            select(
                func.count().filter(ConciergeOffer.status == "accepted"),
                func.count(),
            ).where(
                ConciergeOffer.status.in_(("accepted", "declined", "expired")),
                ConciergeOffer.presented_at >= start,
                ConciergeOffer.presented_at < end,
            )
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "concierge_conversion",
        True,
        numerator,
        denominator,
        _ratio(numerator, denominator),
        "ratio",
    )


async def _care_journey_start(session: AsyncSession, start: datetime, end: datetime) -> KPIResult:
    numerator = (
        await session.execute(
            select(func.count(func.distinct(PetJourney.pet_id))).where(
                PetJourney.started_at >= start, PetJourney.started_at < end
            )
        )
    ).scalar_one()
    denominator = (
        await session.execute(select(func.count()).where(Pet.status == "active"))
    ).scalar_one()
    return KPIResult(
        "care_journey_start",
        True,
        numerator,
        denominator,
        _ratio(numerator, denominator),
        "ratio",
    )


async def _care_journey_completion(
    session: AsyncSession, start: datetime, end: datetime
) -> KPIResult:
    row = (
        await session.execute(
            select(
                func.count().filter(PetJourney.status == "completed"),
                func.count(),
            ).where(
                PetJourney.status.in_(("completed", "stopped")),
                PetJourney.started_at >= start,
                PetJourney.started_at < end,
            )
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "care_journey_completion",
        True,
        numerator,
        denominator,
        _ratio(numerator, denominator),
        "ratio",
    )


async def _inventory_estimate_completeness(
    session: AsyncSession, start: datetime, end: datetime
) -> KPIResult:
    active_estimate = (
        select(literal(1))
        .where(
            FoodEstimate.inventory_unit_id == InventoryUnit.id,
            FoodEstimate.status == "active",
            FoodEstimate.low_days.is_not(None),
            FoodEstimate.high_days.is_not(None),
        )
        .exists()
    )
    row = (
        await session.execute(
            select(func.count().filter(active_estimate), func.count()).where(
                InventoryUnit.state == "opened",
                InventoryUnit.opened_at >= start,
                InventoryUnit.opened_at < end,
            )
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "inventory_estimate_completeness",
        True,
        numerator,
        denominator,
        _ratio(numerator, denominator),
        "ratio",
    )


async def _knowledge_release_health(
    session: AsyncSession, start: datetime, end: datetime
) -> KPIResult:
    published = await session.scalar(
        select(KnowledgeRelease).where(KnowledgeRelease.status == "published")
    )
    if published is None:
        return KPIResult(
            "knowledge_release_health",
            False,
            None,
            None,
            None,
            "ratio",
            data_limitation="No knowledge release currently has status='published'",
        )
    row = (
        await session.execute(
            select(
                func.count().filter(
                    KnowledgeGuidance.review_status == "veterinary_approved",
                    KnowledgeGuidance.app_eligible.is_(True),
                ),
                func.count(),
            ).where(KnowledgeGuidance.release_id == published.id)
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "knowledge_release_health",
        True,
        numerator,
        denominator,
        _ratio(numerator, denominator),
        "ratio",
    )


async def _pi_collection_quality(
    session: AsyncSession, start: datetime, end: datetime
) -> KPIResult:
    row = (
        await session.execute(
            select(
                func.count().filter(ExternalProductMatch.match_status == "approved"),
                func.count(),
            ).where(
                ExternalProductMatch.created_at >= start, ExternalProductMatch.created_at < end
            )
        )
    ).one()
    numerator, denominator = row
    return KPIResult(
        "pi_collection_quality",
        True,
        numerator,
        denominator,
        _ratio(numerator, denominator),
        "ratio",
    )


_COMPUTE: dict[str, Callable[[AsyncSession, datetime, datetime], Awaitable[KPIResult]]] = {
    "conversion": _conversion,
    "payment_success": _payment_success,
    "sourcing_failure": _sourcing_failure,
    "delivery_within_commitment": _delivery_within_commitment,
    "late_credit_issuance": _late_credit_issuance,
    "late_credit_redemption": _late_credit_redemption,
    "repeat_purchase": _repeat_purchase,
    "gmv": _gmv,
    "margin": _margin,
    "reference_price_savings": _reference_price_savings,
    "reorder_recommendation_coverage": _reorder_recommendation_coverage,
    "reorder_approval_rate": _reorder_approval_rate,
    "replenishment_conversion": _replenishment_conversion,
    "concierge_conversion": _concierge_conversion,
    "care_journey_start": _care_journey_start,
    "care_journey_completion": _care_journey_completion,
    "inventory_estimate_completeness": _inventory_estimate_completeness,
    "knowledge_release_health": _knowledge_release_health,
    "pi_collection_quality": _pi_collection_quality,
}

assert set(_COMPUTE) == set(KPI_REGISTRY), "every KPI_REGISTRY key must have a compute function"


async def compute_kpi(
    session: AsyncSession, key: str, *, window_start: datetime, window_end: datetime
) -> KPIResult:
    if key not in KPI_REGISTRY:
        raise KeyError(f"unknown KPI key: {key}")
    return await _COMPUTE[key](session, window_start, window_end)


async def compute_all_kpis(
    session: AsyncSession, *, window_start: datetime, window_end: datetime
) -> list[KPIResult]:
    return [
        await _COMPUTE[key](session, window_start, window_end) for key in KPI_REGISTRY
    ]
