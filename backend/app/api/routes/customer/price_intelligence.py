"""Customer API routes for price intelligence queries."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser
from app.db.session import get_db_session
from app.modules.catalog.models import Offer
from app.modules.price_intelligence.models import ExternalPriceObservation

router = APIRouter(prefix="/price-intelligence", tags=["customers", "price-intelligence"])


class CustomerPriceIntelligenceResponse(BaseModel):
    """Response model for customer price intelligence query."""
    
    offer_id: UUID
    offer_name: str
    our_price_amount: int
    our_price_currency: str
    competitor_price_amount: int | None
    competitor_price_currency: str | None
    competitor_name: str | None
    price_difference_amount: int | None
    price_difference_percentage: float | None
    last_updated: str | None


@router.get("/offers/{offer_id}/competitor-prices", response_model=CustomerPriceIntelligenceResponse)
async def get_offer_competitor_prices(
    offer_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: CurrentUser,
) -> CustomerPriceIntelligenceResponse:
    """
    Get competitor pricing information for a specific offer.
    
    Returns approved external price observations that match our catalog offer.
    Only returns observations with high confidence matches (>= 85).
    """
    # Get our offer
    offer = await session.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offer not found"
        )
    
    # Find approved price observations for this offer
    query = (
        select(ExternalPriceObservation)
        .where(
            ExternalPriceObservation.matched_offer_id == offer_id,
            ExternalPriceObservation.approved_by_admin == True,
            ExternalPriceObservation.match_confidence >= 85,
        )
        .order_by(ExternalPriceObservation.observation_timestamp.desc())
        .limit(1)
    )
    
    result = await session.execute(query)
    observation = result.scalar_one_or_none()
    
    # Build response
    response = CustomerPriceIntelligenceResponse(
        offer_id=offer.id,
        offer_name=offer.name,
        our_price_amount=offer.price_amount,
        our_price_currency=offer.price_currency,
        competitor_price_amount=None,
        competitor_price_currency=None,
        competitor_name=None,
        price_difference_amount=None,
        price_difference_percentage=None,
        last_updated=None,
    )
    
    if observation:
        response.competitor_price_amount = observation.price_amount
        response.competitor_price_currency = observation.price_currency
        response.competitor_name = "external_market"
        response.last_updated = observation.observation_timestamp.isoformat()
        
        # Calculate price difference
        price_diff = observation.price_amount - offer.price_amount
        response.price_difference_amount = price_diff
        response.price_difference_percentage = (price_diff / offer.price_amount) * 100
    
    return response


@router.get("/offers", response_model=list[CustomerPriceIntelligenceResponse])
async def list_offers_with_competitor_prices(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: CurrentUser,
    limit: int = 50,
) -> list[CustomerPriceIntelligenceResponse]:
    """
    List offers with competitor pricing information.
    
    Returns offers that have approved price intelligence observations.
    """
    # Get offers with approved price observations
    query = (
        select(Offer, ExternalPriceObservation)
        .join(
            ExternalPriceObservation,
            ExternalPriceObservation.matched_offer_id == Offer.id
        )
        .where(
            ExternalPriceObservation.approved_by_admin == True,
            ExternalPriceObservation.match_confidence >= 85,
            Offer.status == "active",
        )
        .order_by(ExternalPriceObservation.observation_timestamp.desc())
        .limit(limit)
    )
    
    result = await session.execute(query)
    rows = result.all()
    
    responses = []
    for offer, observation in rows:
        price_diff = observation.price_amount - offer.price_amount
        price_diff_pct = (price_diff / offer.price_amount) * 100
        
        responses.append(
            CustomerPriceIntelligenceResponse(
                offer_id=offer.id,
                offer_name=offer.name,
                our_price_amount=offer.price_amount,
                our_price_currency=offer.price_currency,
                competitor_price_amount=observation.price_amount,
                competitor_price_currency=observation.price_currency,
                competitor_name="external_market",
                price_difference_amount=price_diff,
                price_difference_percentage=price_diff_pct,
                last_updated=observation.observation_timestamp.isoformat(),
            )
        )
    
    return responses
