"""Inert-by-default price-intelligence collection worker."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.price_intelligence.petmall_am import PetmallAmCollector
from app.integrations.price_intelligence.petmall_am_parser import (
    ParsedProductError,
    parse_product_detail_page,
)
from app.integrations.price_intelligence.service import PriceIntelligenceService

logger = logging.getLogger(__name__)


async def run_petmall_am_collection(
    session: AsyncSession,
    settings: Settings,
) -> dict[str, int | str]:
    if not settings.price_intelligence_collection_enabled:
        return {"status": "disabled", "pages": 0, "products": 0, "observations": 0}
    service = PriceIntelligenceService(session)
    source = await service.get_or_create_source(
        PetmallAmCollector.SOURCE_CODE,
        name=PetmallAmCollector.SOURCE_NAME,
        base_url=PetmallAmCollector.BASE_URL,
        country_code=PetmallAmCollector.COUNTRY_CODE,
        default_currency=PetmallAmCollector.CURRENCY_CODE,
    )
    if not service.source_policy_allows_collection(source) or not source.collection_enabled:
        return {"status": "policy_blocked", "pages": 0, "products": 0, "observations": 0}

    async with httpx.AsyncClient() as client:
        collector = PetmallAmCollector(client, settings=settings)
        run = await service.create_collection_run(
            source.id, pages_requested=settings.price_intelligence_max_pages
        )
        pages = products = observations = errors = 0
        try:
            for page_number in range(1, settings.price_intelligence_max_pages + 1):
                urls = await collector.discover_product_urls(page_number)
                pages += 1
                if not urls:
                    break
                for url in urls[: settings.price_intelligence_max_products_per_run - products]:
                    try:
                        page = await collector.fetch_product_detail(url)
                        parsed = parse_product_detail_page(page.content, page.url)
                        _product, observation_result = await service.ingest_parsed_product(
                            source, parsed, collection_run_id=run.id
                        )
                        products += 1
                        observations += 1 if observation_result.created else 0
                    except ParsedProductError:
                        errors += 1
                    except Exception:
                        errors += 1
                        logger.exception("price intelligence product collection failed")
                    if products >= settings.price_intelligence_max_products_per_run:
                        break
                if products >= settings.price_intelligence_max_products_per_run:
                    break
            await service.complete_collection_run(
                run.id,
                status="completed" if errors == 0 else "failed",
                products_seen=products,
                prices_inserted=observations,
                pages_succeeded=pages,
                errors_count=errors,
                error_summary_json={"summary": "some products failed"} if errors else None,
            )
            await session.commit()
            return {
                "status": "completed" if errors == 0 else "failed",
                "pages": pages,
                "products": products,
                "observations": observations,
            }
        except Exception:
            await service.complete_collection_run(
                run.id,
                status="failed",
                products_seen=products,
                prices_inserted=observations,
                pages_succeeded=pages,
                errors_count=errors + 1,
                error_summary_json={"summary": "collection failed"},
            )
            await session.commit()
            raise


run_petsmall_am_collection = run_petmall_am_collection
