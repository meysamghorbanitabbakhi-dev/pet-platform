"""Worker for scheduled price intelligence collection."""
from __future__ import annotations

import logging
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import utc_now
from app.core.config import Settings
from app.integrations.price_intelligence.petmall_am import PetmallAmCollector
from app.integrations.price_intelligence.petmall_am_parser import PetmallAmParser
from app.integrations.price_intelligence.service import PriceIntelligenceService
from app.modules.price_intelligence.models import (
    ExternalPriceObservation,
    ExternalPriceSource,
    ExternalSeller,
)

logger = logging.getLogger(__name__)


async def run_petsmall_am_collection(
    session: AsyncSession,
    settings: Settings,
    max_pages: int = 10,
) -> dict[str, int]:
    """
    Execute price intelligence collection from Petmall Armenia.
    
    Args:
        session: Database session
        settings: Application settings
        max_pages: Maximum number of pages to collect
        
    Returns:
        Dictionary with collection statistics
    """
    if not settings.petsmall_am_enabled:
        logger.info("Petmall.am collection is disabled")
        return {"status": "disabled", "pages": 0, "products": 0, "observations": 0}
    
    logger.info("Starting Petmall.am price intelligence collection")
    
    # Initialize collector and service
    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": settings.price_intelligence_user_agent}
    ) as client:
        collector = PetmallAmCollector(
            client=client,
            request_delay_seconds=settings.price_intelligence_request_delay_seconds,
            max_retries=settings.price_intelligence_max_retries,
        )
        
        # Check robots.txt first
        robots_allowed = await collector.check_robots_txt()
        
        # Get or create source
        source = await session.get(
            ExternalPriceSource,
            "9b9e4da1-113c-4d4d-ae29-dec2a72f7c07"
        )
        
        if source is None:
            source = ExternalPriceSource(
                id="9b9e4da1-113c-4d4d-ae29-dec2a72f7c07",
                code="petsmall_am",
                name="Petmall Armenia",
                base_url="https://www.petmall.am",
                country_code="AM",
                currency_code="AMD",
                collection_enabled=True,
                robots_txt_allowed=robots_allowed,
                robots_txt_checked_at=utc_now(),
                terms_status="accepted",
                terms_checked_at=datetime(2026, 1, 16),
            )
            session.add(source)
            await session.flush()
        else:
            source.robots_txt_allowed = robots_allowed
            source.robots_txt_checked_at = utc_now()
        
        if not robots_allowed:
            logger.warning("Robots.txt disallows collection for Petmall.am")
            await session.commit()
            return {"status": "robots_disallowed", "pages": 0, "products": 0, "observations": 0}
        
        if not source.collection_enabled:
            logger.info("Petmall.am collection is disabled")
            await session.commit()
            return {"status": "disabled", "pages": 0, "products": 0, "observations": 0}
        
        # Get or create seller
        seller = await session.get(
            ExternalSeller,
            "9b9e4da1-113c-4d4d-ae29-dec2a72f7c08"
        )
        
        if seller is None:
            seller = ExternalSeller(
                id="9b9e4da1-113c-4d4d-ae29-dec2a72f7c08",
                source_id="9b9e4da1-113c-4d4d-ae29-dec2a72f7c07",
                name="RoCan Store",
                seller_code="rocan-store",
                seller_type="marketplace_seller",
                is_official=False,
            )
            session.add(seller)
            await session.flush()
        
        # Initialize service
        service = PriceIntelligenceService(session, settings)
        
        # Collect products
        total_pages = 0
        total_products = 0
        total_observations = 0
        
        try:
            async for page_html, page_num, page_url in collector.collect_brand_pages(
                brand_slug="royal-canin",
                max_pages=max_pages
            ):
                total_pages += 1
                logger.info(f"Processing page {page_num}")
                
                # Parse product listings
                parser = PetmallAmParser()
                product_links = await parser.parse_brand_page(page_html)
                
                for product_url in product_links:
                    # Fetch product detail page
                    product_html = await collector.fetch_product_detail(product_url)
                    if product_html is None:
                        continue
                    
                    total_products += 1
                    
                    # Parse product data
                    product_data = await parser.parse_product_page(product_html, product_url)
                    if product_data is None:
                        logger.warning(f"Failed to parse product: {product_url}")
                        continue
                    
                    # Store observation
                    observation = ExternalPriceObservation(
                        source_code="petsmall_am",
                        seller_id="9b9e4da1-113c-4d4d-ae29-dec2a72f7c08",
                        external_sku=product_data.get("sku"),
                        product_name=product_data.get("name", ""),
                        product_url=product_url,
                        price_amount=int(product_data.get("price", 0)),
                        price_currency="AMD",
                        weight_kg=product_data.get("weight_kg"),
                        package_size=product_data.get("package_size"),
                        stock_status="in_stock" if product_data.get("in_stock", False) else "out_of_stock",
                        observation_timestamp=utc_now(),
                        extraction_method="json_ld",
                        confidence_score=100,
                    )
                    
                    # Match to catalog
                    matched = await service.match_observation(observation, product_data)
                    
                    # Store observation
                    await service.update_or_create_observation(observation)
                    total_observations += 1
                    
                    if matched:
                        logger.info(f"Matched {product_data.get('name')} to catalog")
                    else:
                        logger.debug(f"No catalog match for {product_data.get('name')}")
        
        except Exception as e:
            logger.error(f"Error during Petmall.am collection: {e}", exc_info=True)
            await session.commit()
            return {
                "status": "error",
                "pages": total_pages,
                "products": total_products,
                "observations": total_observations,
                "error": str(e)
            }
        
        # Update source statistics
        source.last_successful_collection_at = utc_now()
        source.total_pages_collected = (source.total_pages_collected or 0) + total_pages
        source.total_observations_stored = (source.total_observations_stored or 0) + total_observations
        
        await session.commit()
        
        logger.info(
            f"Petmall.am collection complete: {total_pages} pages, "
            f"{total_products} products, {total_observations} observations"
        )
        
        return {
            "status": "success",
            "pages": total_pages,
            "products": total_products,
            "observations": total_observations
        }
