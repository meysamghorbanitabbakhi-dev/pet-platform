"""Operator API routes for price intelligence management."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentOperator
from app.common.time import utc_now
from app.db.session import get_db_session
from app.integrations.price_intelligence.petmall_am import PetmallAmCollector
from app.integrations.price_intelligence.service import PriceIntelligenceService
from app.modules.price_intelligence.models import (
    ExternalPriceObservation,
    ExternalPriceSource,
    ExternalSeller,
)

router = APIRouter(prefix="/operator/price-intelligence", tags=["operator", "price-intelligence"])


class SourceResponse(BaseModel):
    """Response model for price intelligence source."""
    
    id: UUID
    code: str
    name: str
    base_url: str
    country_code: str
    currency_code: str
    collection_enabled: bool
    robots_txt_allowed: bool | None
    robots_txt_checked_at: str | None
    terms_status: str
    terms_checked_at: str | None
    last_successful_collection_at: str | None
    total_pages_collected: int
    total_observations_stored: int


class ObservationResponse(BaseModel):
    """Response model for price observation."""
    
    id: UUID
    source_code: str
    product_name: str
    product_url: str
    external_sku: str | None
    price_amount: int
    price_currency: str
    stock_status: str
    observation_timestamp: str
    matched_offer_id: UUID | None
    match_confidence: int
    approved_by_admin: bool


class ApproveObservationRequest(BaseModel):
    """Request model for approving an observation."""
    
    approved: bool = Field(..., description="Whether to approve the observation")
    match_confidence_override: int | None = Field(
        None, 
        ge=0, 
        le=100,
        description="Override match confidence score (0-100)"
    )


class UpdateSourceRequest(BaseModel):
    """Request model for updating source configuration."""
    
    collection_enabled: bool = Field(..., description="Whether collection is enabled")


class CheckRobotsTxtResponse(BaseModel):
    """Response model for robots.txt check."""
    
    robots_txt_allowed: bool
    robots_txt_checked_at: str
    robots_txt_disallowed_reason: str | None


@router.get("/sources", response_model=list[SourceResponse])
async def list_price_intelligence_sources(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    operator: CurrentOperator,
) -> list[SourceResponse]:
    """List all price intelligence sources."""
    from sqlalchemy import select
    
    result = await session.execute(select(ExternalPriceSource))
    sources = result.scalars().all()
    
    return [
        SourceResponse(
            id=source.id,
            code=source.code,
            name=source.name,
            base_url=source.base_url,
            country_code=source.country_code,
            currency_code=source.currency_code,
            collection_enabled=source.collection_enabled,
            robots_txt_allowed=source.robots_txt_allowed,
            robots_txt_checked_at=source.robots_txt_checked_at.isoformat() if source.robots_txt_checked_at else None,
            terms_status=source.terms_status,
            terms_checked_at=source.terms_checked_at.isoformat() if source.terms_checked_at else None,
            last_successful_collection_at=source.last_successful_collection_at.isoformat() if source.last_successful_collection_at else None,
            total_pages_collected=source.total_pages_collected,
            total_observations_stored=source.total_observations_stored,
        )
        for source in sources
    ]


@router.get("/sources/{source_id}", response_model=SourceResponse)
async def get_price_intelligence_source(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    operator: CurrentOperator,
) -> SourceResponse:
    """Get a specific price intelligence source."""
    source = await session.get(ExternalPriceSource, source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price intelligence source not found"
        )
    
    return SourceResponse(
        id=source.id,
        code=source.code,
        name=source.name,
        base_url=source.base_url,
        country_code=source.country_code,
        currency_code=source.currency_code,
        collection_enabled=source.collection_enabled,
        robots_txt_allowed=source.robots_txt_allowed,
        robots_txt_checked_at=source.robots_txt_checked_at.isoformat() if source.robots_txt_checked_at else None,
        terms_status=source.terms_status,
        terms_checked_at=source.terms_checked_at.isoformat() if source.terms_checked_at else None,
        last_successful_collection_at=source.last_successful_collection_at.isoformat() if source.last_successful_collection_at else None,
        total_pages_collected=source.total_pages_collected,
        total_observations_stored=source.total_observations_stored,
    )


@router.patch("/sources/{source_id}", response_model=SourceResponse)
async def update_price_intelligence_source(
    source_id: UUID,
    request: UpdateSourceRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    operator: CurrentOperator,
) -> SourceResponse:
    """Update a price intelligence source configuration."""
    source = await session.get(ExternalPriceSource, source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price intelligence source not found"
        )
    
    source.collection_enabled = request.collection_enabled
    await session.commit()
    
    return SourceResponse(
        id=source.id,
        code=source.code,
        name=source.name,
        base_url=source.base_url,
        country_code=source.country_code,
        currency_code=source.currency_code,
        collection_enabled=source.collection_enabled,
        robots_txt_allowed=source.robots_txt_allowed,
        robots_txt_checked_at=source.robots_txt_checked_at.isoformat() if source.robots_txt_checked_at else None,
        terms_status=source.terms_status,
        terms_checked_at=source.terms_checked_at.isoformat() if source.terms_checked_at else None,
        last_successful_collection_at=source.last_successful_collection_at.isoformat() if source.last_successful_collection_at else None,
        total_pages_collected=source.total_pages_collected,
        total_observations_stored=source.total_observations_stored,
    )


@router.post("/sources/{source_id}/check-robots", response_model=CheckRobotsTxtResponse)
async def check_robots_txt(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    operator: CurrentOperator,
) -> CheckRobotsTxtResponse:
    """Manually trigger robots.txt check for a source."""
    source = await session.get(ExternalPriceSource, source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price intelligence source not found"
        )
    
    if source.code != "petsmall_am":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Robots.txt check only supported for petsmall_am"
        )
    
    # Perform robots.txt check
    import httpx
    from app.core.config import get_settings
    
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": settings.price_intelligence_user_agent}
    ) as client:
        collector = PetmallAmCollector(
            client=client,
            request_delay_seconds=settings.price_intelligence_request_delay_seconds,
            max_retries=settings.price_intelligence_max_retries,
        )
        
        allowed, reason = await collector.check_robots_txt()
    
    # Update source
    source.robots_txt_allowed = allowed
    source.robots_txt_checked_at = utc_now()
    await session.commit()
    
    return CheckRobotsTxtResponse(
        robots_txt_allowed=allowed,
        robots_txt_checked_at=source.robots_txt_checked_at.isoformat(),
        robots_txt_disallowed_reason=reason,
    )


@router.get("/observations", response_model=list[ObservationResponse])
async def list_price_observations(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    operator: CurrentOperator,
    source_code: str | None = None,
    approved_only: bool = False,
    limit: int = 100,
) -> list[ObservationResponse]:
    """List price observations with optional filters."""
    from sqlalchemy import select
    
    query = select(ExternalPriceObservation).limit(limit)
    
    if source_code:
        query = query.where(ExternalPriceObservation.source_code == source_code)
    
    if approved_only:
        query = query.where(ExternalPriceObservation.approved_by_admin == True)
    
    query = query.order_by(ExternalPriceObservation.observation_timestamp.desc())
    
    result = await session.execute(query)
    observations = result.scalars().all()
    
    return [
        ObservationResponse(
            id=obs.id,
            source_code=obs.source_code,
            product_name=obs.product_name,
            product_url=obs.product_url,
            external_sku=obs.external_sku,
            price_amount=obs.price_amount,
            price_currency=obs.price_currency,
            stock_status=obs.stock_status,
            observation_timestamp=obs.observation_timestamp.isoformat(),
            matched_offer_id=obs.matched_offer_id,
            match_confidence=obs.match_confidence,
            approved_by_admin=obs.approved_by_admin,
        )
        for obs in observations
    ]


@router.post("/observations/{observation_id}/approve", response_model=ObservationResponse)
async def approve_observation(
    observation_id: UUID,
    request: ApproveObservationRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    operator: CurrentOperator,
) -> ObservationResponse:
    """Approve or reject a price observation."""
    observation = await session.get(ExternalPriceObservation, observation_id)
    if observation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price observation not found"
        )
    
    observation.approved_by_admin = request.approved
    if request.match_confidence_override is not None:
        observation.match_confidence = request.match_confidence_override
    
    await session.commit()
    
    return ObservationResponse(
        id=observation.id,
        source_code=observation.source_code,
        product_name=observation.product_name,
        product_url=observation.product_url,
        external_sku=observation.external_sku,
        price_amount=observation.price_amount,
        price_currency=observation.price_currency,
        stock_status=observation.stock_status,
        observation_timestamp=observation.observation_timestamp.isoformat(),
        matched_offer_id=observation.matched_offer_id,
        match_confidence=observation.match_confidence,
        approved_by_admin=observation.approved_by_admin,
    )


@router.delete("/observations/{observation_id}")
async def delete_observation(
    observation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    operator: CurrentOperator,
) -> dict[str, str]:
    """Delete a price observation."""
    observation = await session.get(ExternalPriceObservation, observation_id)
    if observation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price observation not found"
        )
    
    await session.delete(observation)
    await session.commit()
    
    return {"status": "deleted", "id": str(observation_id)}
