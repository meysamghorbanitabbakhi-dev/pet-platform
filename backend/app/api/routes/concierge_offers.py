from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.contracts import (
    ConciergeOfferOperatorResponse,
    ConciergeOfferResponse,
    OffsetPage,
)
from app.api.dependencies import CurrentIdentity, CurrentOperator
from app.api.pagination import Pagination, page
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.modules.catalog.models import Supplier
from app.modules.concierge.models import ConciergeOffer
from app.modules.concierge.service import (
    ConciergeOfferError,
    OfferPresentationFacts,
    accept_offer,
    decline_offer,
    mark_unavailable,
    present_offer,
    promote_to_catalog,
    request_refresh,
    start_review,
)
from app.modules.support.models import CustomerRequest

router = APIRouter(tags=["concierge-offers"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
PaginationDependency = Annotated[Pagination, Depends()]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def _require_enabled(settings: Settings) -> None:
    if not settings.concierge_offers_enabled:
        raise HTTPException(status_code=409, detail="concierge_offers_disabled")


class ConciergeOfferAcceptBody(BaseModel):
    address_id: UUID


class ConciergeOfferDeclineBody(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ConciergeOfferUnavailableBody(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class ConciergeOfferPromoteBody(BaseModel):
    rationale: str = Field(min_length=5, max_length=2000)


class OfferPresentationBody(BaseModel):
    title_fa: str = Field(min_length=1, max_length=300)
    unit_label_fa: str = Field(min_length=1, max_length=100)
    quantity: int = Field(default=1, ge=1, le=100)
    authenticity_basis: str = Field(min_length=1, max_length=50)
    supplier_id: UUID
    verification_evidence_file_id: UUID
    minimum_shelf_life_months: int = Field(ge=1, le=36)
    estimated_delivery_days: int = Field(ge=1, le=180)
    pricing_mode: str
    price_irr: int = Field(gt=0)
    price_explanation_fa: str = Field(min_length=1, max_length=2000)
    reference_price_irr: int | None = Field(default=None, gt=0)
    supplier_cost_irr: int | None = Field(default=None, gt=0)
    exchange_rate_basis_irr_per_unit: int | None = Field(default=None, gt=0)
    international_transport_irr: int | None = Field(default=None, gt=0)
    customs_clearance_irr: int | None = Field(default=None, gt=0)
    handling_irr: int | None = Field(default=None, gt=0)
    domestic_delivery_irr: int | None = Field(default=None, gt=0)
    payment_fees_irr: int | None = Field(default=None, gt=0)
    risk_reserve_irr: int | None = Field(default=None, gt=0)
    platform_margin_irr: int | None = Field(default=None, gt=0)
    validity_hours: int | None = Field(default=None, ge=12, le=48)


async def _customer_offer_response(
    session: AsyncSession, offer: ConciergeOffer
) -> ConciergeOfferResponse:
    supplier_country_code = None
    if offer.supplier_id is not None:
        supplier_country_code = await session.scalar(
            select(Supplier.country_code).where(Supplier.id == offer.supplier_id)
        )
    return ConciergeOfferResponse(
        id=offer.id,
        request_id=offer.request_id,
        refreshed_from_offer_id=offer.refreshed_from_offer_id,
        status=offer.status,
        title_fa=offer.title_fa,
        unit_label_fa=offer.unit_label_fa,
        quantity=offer.quantity,
        authenticity_basis=offer.authenticity_basis,
        supplier_country_code=supplier_country_code,
        minimum_shelf_life_months=offer.minimum_shelf_life_months,
        estimated_delivery_days=offer.estimated_delivery_days,
        pricing_mode=offer.pricing_mode,
        price_irr=offer.price_irr,
        reference_price_irr=offer.reference_price_irr,
        price_explanation_fa=offer.price_explanation_fa,
        presented_at=offer.presented_at,
        expires_at=offer.expires_at,
        responded_at=offer.responded_at,
        decline_reason=offer.decline_reason,
        unavailable_reason=offer.unavailable_reason,
        resulting_order_id=offer.resulting_order_id,
    )


def _operator_offer_response(offer: ConciergeOffer) -> ConciergeOfferOperatorResponse:
    return ConciergeOfferOperatorResponse(
        id=offer.id,
        request_id=offer.request_id,
        household_id=offer.household_id,
        customer_identity_id=offer.customer_identity_id,
        refreshed_from_offer_id=offer.refreshed_from_offer_id,
        status=offer.status,
        reviewing_started_at=offer.reviewing_started_at,
        title_fa=offer.title_fa,
        unit_label_fa=offer.unit_label_fa,
        quantity=offer.quantity,
        authenticity_basis=offer.authenticity_basis,
        supplier_id=offer.supplier_id,
        verification_evidence_file_id=offer.verification_evidence_file_id,
        minimum_shelf_life_months=offer.minimum_shelf_life_months,
        estimated_delivery_days=offer.estimated_delivery_days,
        pricing_mode=offer.pricing_mode,
        price_irr=offer.price_irr,
        reference_price_irr=offer.reference_price_irr,
        price_explanation_fa=offer.price_explanation_fa,
        supplier_cost_irr=offer.supplier_cost_irr,
        exchange_rate_basis_irr_per_unit=offer.exchange_rate_basis_irr_per_unit,
        international_transport_irr=offer.international_transport_irr,
        customs_clearance_irr=offer.customs_clearance_irr,
        handling_irr=offer.handling_irr,
        domestic_delivery_irr=offer.domestic_delivery_irr,
        payment_fees_irr=offer.payment_fees_irr,
        risk_reserve_irr=offer.risk_reserve_irr,
        platform_margin_irr=offer.platform_margin_irr,
        presented_at=offer.presented_at,
        validity_hours=offer.validity_hours,
        expires_at=offer.expires_at,
        responded_at=offer.responded_at,
        decline_reason=offer.decline_reason,
        unavailable_reason=offer.unavailable_reason,
        promoted_offer_id=offer.promoted_offer_id,
        resulting_order_id=offer.resulting_order_id,
        catalog_promoted_at=offer.catalog_promoted_at,
        catalog_promotion_rationale=offer.catalog_promotion_rationale,
    )


# --- customer-facing ---------------------------------------------------


@router.get(
    "/customer-requests/{request_id}/concierge-offers",
    response_model=list[ConciergeOfferResponse],
)
async def list_concierge_offers(
    request_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> list[ConciergeOfferResponse]:
    _require_enabled(settings)
    request = await session.get(CustomerRequest, request_id)
    if request is None or request.identity_id != identity.id:
        raise HTTPException(status_code=404, detail="customer_request_not_found")
    rows = list(
        (
            await session.scalars(
                select(ConciergeOffer)
                .where(ConciergeOffer.request_id == request_id)
                .order_by(ConciergeOffer.created_at.desc())
            )
        ).all()
    )
    return [await _customer_offer_response(session, row) for row in rows]


@router.get("/concierge-offers/{offer_id}", response_model=ConciergeOfferResponse)
async def get_concierge_offer(
    offer_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ConciergeOfferResponse:
    _require_enabled(settings)
    offer = await session.get(ConciergeOffer, offer_id)
    if offer is None or offer.customer_identity_id != identity.id:
        raise HTTPException(status_code=404, detail="concierge_offer_not_found")
    return await _customer_offer_response(session, offer)


@router.post("/concierge-offers/{offer_id}/accept", response_model=ConciergeOfferResponse)
async def accept_concierge_offer(
    offer_id: UUID,
    body: ConciergeOfferAcceptBody,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ConciergeOfferResponse:
    _require_enabled(settings)
    offer = await session.scalar(
        select(ConciergeOffer).where(ConciergeOffer.id == offer_id).with_for_update()
    )
    if offer is None or offer.customer_identity_id != identity.id:
        raise HTTPException(status_code=404, detail="concierge_offer_not_found")
    try:
        offer, _ = await accept_offer(
            session,
            offer=offer,
            customer_identity_id=identity.id,
            address_id=body.address_id,
        )
    except ConciergeOfferError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await _customer_offer_response(session, offer)


@router.post("/concierge-offers/{offer_id}/decline", response_model=ConciergeOfferResponse)
async def decline_concierge_offer(
    offer_id: UUID,
    body: ConciergeOfferDeclineBody,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ConciergeOfferResponse:
    _require_enabled(settings)
    offer = await session.scalar(
        select(ConciergeOffer).where(ConciergeOffer.id == offer_id).with_for_update()
    )
    if offer is None or offer.customer_identity_id != identity.id:
        raise HTTPException(status_code=404, detail="concierge_offer_not_found")
    try:
        offer = await decline_offer(
            session, offer=offer, customer_identity_id=identity.id, reason=body.reason
        )
    except ConciergeOfferError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return await _customer_offer_response(session, offer)


@router.post("/concierge-offers/{offer_id}/refresh", response_model=ConciergeOfferResponse)
async def refresh_concierge_offer(
    offer_id: UUID,
    identity: CurrentIdentity,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ConciergeOfferResponse:
    _require_enabled(settings)
    offer = await session.scalar(
        select(ConciergeOffer).where(ConciergeOffer.id == offer_id).with_for_update()
    )
    if offer is None or offer.customer_identity_id != identity.id:
        raise HTTPException(status_code=404, detail="concierge_offer_not_found")
    try:
        refreshed = await request_refresh(
            session, expired_offer=offer, customer_identity_id=identity.id
        )
    except ConciergeOfferError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return await _customer_offer_response(session, refreshed)


# --- operator-facing -----------------------------------------------------


@router.get("/operator/concierge-offers", response_model=OffsetPage[ConciergeOfferOperatorResponse])
async def operator_list_concierge_offers(
    _: CurrentOperator,
    session: SessionDependency,
    pagination: PaginationDependency,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> OffsetPage[ConciergeOfferOperatorResponse]:
    filters = (ConciergeOffer.status == status_filter,) if status_filter else ()
    total = int(
        await session.scalar(select(func.count(ConciergeOffer.id)).where(*filters)) or 0
    )
    rows = list(
        (
            await session.scalars(
                select(ConciergeOffer)
                .where(*filters)
                .order_by(ConciergeOffer.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.limit)
            )
        ).all()
    )
    return OffsetPage[ConciergeOfferOperatorResponse].model_validate(
        page(
            [_operator_offer_response(row) for row in rows],
            total=total,
            pagination=pagination,
        )
    )


@router.get(
    "/operator/concierge-offers/{offer_id}", response_model=ConciergeOfferOperatorResponse
)
async def operator_get_concierge_offer(
    offer_id: UUID, _: CurrentOperator, session: SessionDependency
) -> ConciergeOfferOperatorResponse:
    offer = await session.get(ConciergeOffer, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="concierge_offer_not_found")
    return _operator_offer_response(offer)


@router.post(
    "/operator/customer-requests/{request_id}/concierge-offers/start-review",
    response_model=ConciergeOfferOperatorResponse,
)
async def operator_start_review(
    request_id: UUID,
    operator: CurrentOperator,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ConciergeOfferOperatorResponse:
    _require_enabled(settings)
    request = await session.get(CustomerRequest, request_id, with_for_update=True)
    if request is None:
        raise HTTPException(status_code=404, detail="customer_request_not_found")
    try:
        offer = await start_review(session, request=request, operator_id=operator.id)
    except ConciergeOfferError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return _operator_offer_response(offer)


@router.post(
    "/operator/concierge-offers/{offer_id}/present",
    response_model=ConciergeOfferOperatorResponse,
)
async def operator_present_offer(
    offer_id: UUID,
    body: OfferPresentationBody,
    operator: CurrentOperator,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ConciergeOfferOperatorResponse:
    _require_enabled(settings)
    offer = await session.scalar(
        select(ConciergeOffer).where(ConciergeOffer.id == offer_id).with_for_update()
    )
    if offer is None:
        raise HTTPException(status_code=404, detail="concierge_offer_not_found")
    facts = OfferPresentationFacts(
        title_fa=body.title_fa,
        unit_label_fa=body.unit_label_fa,
        quantity=body.quantity,
        authenticity_basis=body.authenticity_basis,
        supplier_id=body.supplier_id,
        verification_evidence_file_id=body.verification_evidence_file_id,
        minimum_shelf_life_months=body.minimum_shelf_life_months,
        estimated_delivery_days=body.estimated_delivery_days,
        pricing_mode=body.pricing_mode,
        price_irr=body.price_irr,
        price_explanation_fa=body.price_explanation_fa,
        reference_price_irr=body.reference_price_irr,
        supplier_cost_irr=body.supplier_cost_irr,
        exchange_rate_basis_irr_per_unit=body.exchange_rate_basis_irr_per_unit,
        international_transport_irr=body.international_transport_irr,
        customs_clearance_irr=body.customs_clearance_irr,
        handling_irr=body.handling_irr,
        domestic_delivery_irr=body.domestic_delivery_irr,
        payment_fees_irr=body.payment_fees_irr,
        risk_reserve_irr=body.risk_reserve_irr,
        platform_margin_irr=body.platform_margin_irr,
        validity_hours=body.validity_hours or settings.concierge_offer_default_validity_hours,
    )
    try:
        offer = await present_offer(session, offer=offer, operator_id=operator.id, facts=facts)
    except ConciergeOfferError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return _operator_offer_response(offer)


@router.post(
    "/operator/concierge-offers/{offer_id}/unavailable",
    response_model=ConciergeOfferOperatorResponse,
)
async def operator_mark_unavailable(
    offer_id: UUID,
    body: ConciergeOfferUnavailableBody,
    operator: CurrentOperator,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ConciergeOfferOperatorResponse:
    _require_enabled(settings)
    offer = await session.scalar(
        select(ConciergeOffer).where(ConciergeOffer.id == offer_id).with_for_update()
    )
    if offer is None:
        raise HTTPException(status_code=404, detail="concierge_offer_not_found")
    try:
        offer = await mark_unavailable(
            session, offer=offer, operator_id=operator.id, reason=body.reason
        )
    except ConciergeOfferError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return _operator_offer_response(offer)


@router.post(
    "/operator/concierge-offers/{offer_id}/promote",
    response_model=ConciergeOfferOperatorResponse,
)
async def operator_promote_offer(
    offer_id: UUID,
    body: ConciergeOfferPromoteBody,
    operator: CurrentOperator,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ConciergeOfferOperatorResponse:
    _require_enabled(settings)
    offer = await session.scalar(
        select(ConciergeOffer).where(ConciergeOffer.id == offer_id).with_for_update()
    )
    if offer is None:
        raise HTTPException(status_code=404, detail="concierge_offer_not_found")
    try:
        await promote_to_catalog(
            session, offer=offer, operator_id=operator.id, rationale=body.rationale
        )
    except ConciergeOfferError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return _operator_offer_response(offer)
