"""Scheduled entry point for price-intelligence collection."""

from __future__ import annotations

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.integrations.price_intelligence.worker import run_petmall_am_collection


async def run_price_intelligence_collection() -> dict[str, int | str]:
    settings = get_settings()
    async with SessionFactory() as session:
        return await run_petmall_am_collection(session, settings)


run_petsmall_am_collection = run_price_intelligence_collection
