"""Operator-only price-intelligence routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

import httpx
from app.api.dependencies import CurrentOperator
from app.api.middleware import request_id_context
from app.common.time import utc_now
from app.core.config import get_settings
from app.db.session import get_db_session
from app.integrations.price_intelligence.petmall_am import PetmallAmCollector, RobotsTxtError
from app.integrations.price_intelligence.service import PriceIntelligenceService
from app.modules.price_intelligence.models import (
    ExternalPriceObservation,
    ExternalPriceSource,
    ExternalProduct,
)
from app.modules.system.audit import record_operator_action
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/operator/price-intelligence", tags=["operator", "price-intelligence"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


class Page(BaseModel):
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SourceResponse(BaseModel):
    id: UUID
    code: str
    name: str
    base_url: str
    country_code: str
    default_currency: str
    collection_enabled: bool
    robots_status: str
    robots_checked_at: datetime | None
    terms_status: str
    terms_checked_at: datetime | None
    terms_evidence_url: str | None
    last_successful_collection_at: datetime | None


class SourcePolicyUpdate(BaseModel):
    collection_enabled: bool | None = None
    terms_status: Literal["unchecked", "accepted", "rejected", "failed"] | None = None
    terms_evidence_url: str | None = Field(default=None, max_length=1000)
    reason: str = Field(min_length=5, max_length=1000)


class RobotsCheckResponse(BaseModel):
    robots_status: str
    robots_checked_at: datetime
    reason: str | None


class CollectionRunResponse(BaseModel):
    id: UUID
    source_id: UUID
    started_at: datetime
    completed_at: datetime | None
    status: str
    pages_succeeded: int
    products_seen: int
    prices_inserted: int
    errors_count: int


class ObservationResponse(BaseModel):
    id: UUID
    external_product_id: UUID
    seller_id: UUID | None
    currency: str
    currency_exponent: int
    price_minor: int
    availability: str
    observed_at: datetime
    raw_price_text: str | None


class MatchResponse(BaseModel):
    id: UUID
    external_product_id: UUID
    canonical_product_id: UUID | None
    canonical_variant_id: UUID | None
    match_method: str
    match_status: str
    match_confidence: float
    match_reasons_json: dict[str, object] | None
    reviewed_at: datetime | None


class MatchDecisionBody(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class MatchRemapBody(MatchDecisionBody):
    canonical_product_id: UUID
    canonical_variant_id: UUID | None = None


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(
    session: SessionDep,
    operator: CurrentOperator,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[SourceResponse]:
    del operator
    result = await session.execute(select(ExternalPriceSource).offset(offset).limit(limit))
    return [
        SourceResponse.model_validate(source, from_attributes=True)
        for source in result.scalars()
    ]


@router.get("/sources/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: UUID, session: SessionDep, operator: CurrentOperator
) -> SourceResponse:
    del operator
    source = await session.get(ExternalPriceSource, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return SourceResponse.model_validate(source, from_attributes=True)


@router.patch("/sources/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: UUID,
    body: SourcePolicyUpdate,
    session: SessionDep,
    operator: CurrentOperator,
) -> SourceResponse:
    service = PriceIntelligenceService(session)
    try:
        source = await service.update_source_policy(
            source_id,
            collection_enabled=body.collection_enabled,
            terms_status=body.terms_status,
            terms_checked_at=utc_now() if body.terms_status else None,
            terms_evidence_url=body.terms_evidence_url,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    record_operator_action(
        session,
        operator_identity_id=operator.id,
        action="price_intelligence_source_policy_updated",
        resource_type="price_intelligence_source",
        resource_id=str(source.id),
        request_id=request_id_context.get() or "unknown",
        reason=body.reason,
        before_facts=None,
        after_facts={"collection_enabled": source.collection_enabled},
        source_ip=None,
    )
    await session.commit()
    return SourceResponse.model_validate(source, from_attributes=True)


@router.post("/sources/{source_id}/check-robots", response_model=RobotsCheckResponse)
async def check_robots(
    source_id: UUID,
    session: SessionDep,
    operator: CurrentOperator,
) -> RobotsCheckResponse:
    source = await session.get(ExternalPriceSource, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    settings = get_settings()
    status_value = "failed"
    robots_reason: str | None = "robots_fetch_failed"
    async with httpx.AsyncClient() as client:
        collector = PetmallAmCollector(client, settings=settings)
        try:
            allowed, robots_reason = await collector.check_robots_txt()
            status_value = "allowed" if allowed else "disallowed"
        except RobotsTxtError:
            status_value = "failed"
    source.robots_status = status_value
    source.robots_checked_at = utc_now()
    record_operator_action(
        session,
        operator_identity_id=operator.id,
        action="price_intelligence_robots_checked",
        resource_type="price_intelligence_source",
        resource_id=str(source.id),
        request_id=request_id_context.get() or "unknown",
        reason=status_value,
        before_facts=None,
        after_facts={"robots_status": status_value},
        source_ip=None,
    )
    await session.commit()
    return RobotsCheckResponse(
        robots_status=status_value,
        robots_checked_at=source.robots_checked_at,
        reason=robots_reason,
    )


@router.get("/collection-runs", response_model=list[CollectionRunResponse])
async def list_runs(
    session: SessionDep,
    operator: CurrentOperator,
    source_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[CollectionRunResponse]:
    del operator
    runs = await PriceIntelligenceService(session).list_collection_runs(source_id, limit)
    return [CollectionRunResponse.model_validate(run, from_attributes=True) for run in runs]


@router.get("/observations", response_model=list[ObservationResponse])
async def list_observations(
    session: SessionDep,
    operator: CurrentOperator,
    external_product_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ObservationResponse]:
    del operator
    stmt = select(ExternalPriceObservation).order_by(ExternalPriceObservation.observed_at.desc())
    if external_product_id:
        stmt = stmt.where(ExternalPriceObservation.external_product_id == external_product_id)
    result = await session.execute(stmt.limit(limit))
    return [
        ObservationResponse.model_validate(obs, from_attributes=True)
        for obs in result.scalars()
    ]


@router.get("/matches/pending", response_model=list[MatchResponse])
async def list_pending_matches(
    session: SessionDep,
    operator: CurrentOperator,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[MatchResponse]:
    del operator
    matches = await PriceIntelligenceService(session).list_pending_matches(limit)
    return [MatchResponse.model_validate(match, from_attributes=True) for match in matches]


@router.post("/matches/{match_id}/approve", response_model=MatchResponse)
async def approve_match(
    match_id: UUID,
    body: MatchDecisionBody,
    session: SessionDep,
    operator: CurrentOperator,
) -> MatchResponse:
    match = await PriceIntelligenceService(session).approve_match(
        match_id, operator.id, reason=body.reason
    )
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await session.commit()
    return MatchResponse.model_validate(match, from_attributes=True)


@router.post("/matches/{match_id}/reject", response_model=MatchResponse)
async def reject_match(
    match_id: UUID,
    body: MatchDecisionBody,
    session: SessionDep,
    operator: CurrentOperator,
) -> MatchResponse:
    match = await PriceIntelligenceService(session).reject_match(
        match_id, operator.id, reason=body.reason
    )
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await session.commit()
    return MatchResponse.model_validate(match, from_attributes=True)


@router.post("/matches/{match_id}/remap", response_model=MatchResponse)
async def remap_match(
    match_id: UUID,
    body: MatchRemapBody,
    session: SessionDep,
    operator: CurrentOperator,
) -> MatchResponse:
    try:
        match = await PriceIntelligenceService(session).remap_match(
            match_id,
            operator.id,
            canonical_product_id=body.canonical_product_id,
            canonical_variant_id=body.canonical_variant_id,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await session.commit()
    return MatchResponse.model_validate(match, from_attributes=True)


@router.get(
    "/external-products/{external_product_id}/price-history",
    response_model=list[ObservationResponse],
)
async def price_history(
    external_product_id: UUID,
    session: SessionDep,
    operator: CurrentOperator,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[ObservationResponse]:
    del operator
    if await session.get(ExternalProduct, external_product_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    history = await PriceIntelligenceService(session).get_product_price_history(
        external_product_id, limit
    )
    return [ObservationResponse.model_validate(obs, from_attributes=True) for obs in history]
