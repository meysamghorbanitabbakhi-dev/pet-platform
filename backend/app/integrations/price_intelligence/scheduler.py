"""Scheduled price intelligence collection task."""
from __future__ import annotations

import logging
from datetime import timedelta

import httpx

from app.common.time import utc_now
from app.core.config import get_settings
from app.db.session import SessionFactory, get_session
from app.integrations.price_intelligence.petmall_am import PetmallAmCollector
from app.integrations.price_intelligence.petmall_am_parser import PetmallAmParser
from app.integrations.price_intelligence.service import PriceIntelligenceService

logger = logging.getLogger(__name__)


async def run_petsmall_am_collection(
    max_pages: int = 5,
    delay_seconds: float = 2.0,
) -> tuple[int, int]:
    """
    Run price intelligence collection from Petmall Armenia.
    
    Returns:
        Tuple of (products_collected, products_matched)
    """
    settings = get_settings()
    
    if not settings.petsmall_am_enabled:
        logger.info("Petmall Armenia collection is disabled")
        return 0, 0

    logger.info("Starting Petmall Armenia price intelligence collection")

    async with SessionFactory() as session:
        async with get_session() as session_factory:
            service = PriceIntelligenceService(session_factory)
            
            # Ensure source exists and check robots.txt
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                collector = PetmallAmCollector(http_client)
                
                # Check robots.txt
                robots_allowed = await collector.check_robots_txt()
                source = await service.ensure_petsmall_am_source(
                    robots_txt_allowed=robots_allowed,
                    robots_txt_checked_at=utc_now(),
                )
                
                if not source.enabled:
                    logger.info("Petmall Armenia source is disabled, skipping collection")
                    return 0, 0
                
                if not robots_allowed:
                    logger.warning("Robots.txt disallows collection, skipping")
                    return 0, 0
                
                # Ensure default seller exists (RoCan Store)
                seller = await service.ensure_seller(
                    source_id=source.id,
                    seller_name="RoCan Store",
                    seller_code="rocan-store",
                    seller_url="https://petmall.am/en/stores/rocan-store",
                    seller_type="marketplace_seller",
                    is_official=False,
                )
                
                # Collect products from brand pages
                products_collected = 0
                products_matched = 0
                
                for page_num in range(1, max_pages + 1):
                    logger.info("Collecting page %d", page_num)
                    
                    try:
                        # Fetch brand page
                        page_html = await collector.fetch_brand_page(
                            brand_slug="royal-canin",
                            page=page_num,
                        )
                        
                        if not page_html:
                            logger.info("No more pages available at page %d", page_num)
                            break
                        
                        # Parse product URLs from listing
                        parser = PetmallAmParser(
                            source_page_url=f"https://petmall.am/en/brands/royal-canin?page={page_num}"
                        )
                        product_urls = parser.parse_listing_page(page_html)
                        
                        logger.info("Found %d product URLs on page %d", len(product_urls), page_num)
                        
                        # Fetch and parse each product detail page
                        for product_url in product_urls:
                            try:
                                product_html = await collector.fetch_product_detail(product_url)
                                
                                # Parse JSON-LD data
                                detail_parser = PetmallAmParser(source_page_url=product_url)
                                parsed_product = detail_parser.parse_json_ld(product_html)
                                
                                if parsed_product is None:
                                    logger.warning("No JSON-LD data found for %s", product_url)
                                    continue
                                
                                # Create observation
                                observation = await service.create_observation(
                                    parsed_product=parsed_product,
                                    source_id=source.id,
                                    seller_id=seller.id,
                                )
                                
                                products_collected += 1
                                
                                if observation.matched_sku is not None:
                                    products_matched += 1
                
                            except Exception as exc:
                                logger.error("Failed to collect product %s: %s", product_url, exc)
                                
                            # Delay between requests
                            import asyncio
                            if delay_seconds > 0:
                                await asyncio.sleep(delay_seconds)
                    
                    except Exception as exc:
                        logger.error("Failed to collect page %d: %s", page_num, exc)
                        # Stop on first page failure (might be blocked)
                        break
                    
                    # Delay between pages
                    import asyncio
                    if delay_seconds > 0 and page_num < max_pages:
                        await asyncio.sleep(delay_seconds)
                
                # Update source status
                if products_collected > 0:
                    await service.update_source_status(
                        source_id=source.id,
                        last_successful_collection_at=utc_now(),
                    )
                
                await session_factory.commit()
                
                # Schedule auto-approval for high-confidence matches
                await _schedule_auto_approvals(session_factory, seller.id)
                
                logger.info(
                    "Collection complete: %d products collected, %d matched to catalog",
                    products_collected,
                    products_matched,
                )
                
                return products_collected, products_matched


async def _schedule_auto_approvals(session, seller_id) -> None:
    """Schedule auto-approval for high-confidence matches."""
    from sqlalchemy import select
    from app.modules.price_intelligence.models import PriceIntelligenceObservation
    
    # Find pending observations with high confidence
    query = (
        select(PriceIntelligenceObservation)
        .where(
            PriceIntelligenceObservation.seller_id == seller_id,
            PriceIntelligenceObservation.approval_status == "pending",
            PriceIntelligenceObservation.match_confidence >= 90,
        )
    )
    result = await session.execute(query)
    observations = result.scalars().all()
    
    if not observations:
        return
    
    # Auto-approve with system operator
    system_operator_id = "00000000-0000-0000-0000-000000000000"
    
    for obs in observations:
        obs.approval_status = "approved"
        obs.approved_by_operator_id = system_operator_id
        obs.approved_at = utc_now()
        obs.approval_notes = "Auto-approved: high confidence match (>=90%)"
    
    await session.commit()
    logger.info("Auto-approved %d high-confidence observations", len(observations))
