from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import app.db.models  # noqa: F401
import pytest
from alembic import command
from alembic.config import Config
from app.db.session import SessionFactory, close_database
from app.integrations.price_intelligence.service import PriceIntelligenceService
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL is required",
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
_MATCHES_TABLE = "price_intelligence_external_product_matches"
_REVISION = "20260717_0025"
_DOWN_REVISION = "20260716_0024"


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    # SessionFactory's engine binds to the event loop of its first
    # connection. asyncio.run() opens a fresh loop every call, so the engine
    # must be disposed inside the SAME loop it was created in, before that
    # loop closes -- otherwise the next asyncio.run() call reuses a
    # now-invalid connection bound to a closed loop (see the identical note
    # on test_price_observation_idempotency.py's dispose fixture).
    async def _with_dispose() -> T:
        try:
            return await coro
        finally:
            await close_database()

    return asyncio.run(_with_dispose())


async def _seed_unmatched_row() -> None:
    async with SessionFactory() as session:
        service = PriceIntelligenceService(session)
        token = uuid.uuid4().hex
        source = await service.get_or_create_source(
            f"downgrade-test-{token}",
            name="Downgrade test source",
            base_url="https://example.test",
            country_code="AM",
            default_currency="AMD",
        )
        seller = await service.get_or_create_seller(source.id, seller_name=f"seller-{token}")
        product, _ = await service.upsert_external_product(
            source.id,
            f"product-{token}",
            source_url=f"https://example.test/{token}",
            source_title=f"Unmatched downgrade-test food {token}",
            brand_name=f"Nonexistent downgrade-test brand {token}",
            seller_id=seller.id,
        )
        result = await service.run_match_for_product(product)
        assert result.method.value == "unmatched", (
            "test setup assumes a fresh, unrecognizable product does not match any "
            "canonical product; got a real match instead, which would invalidate this test"
        )
        await session.commit()


async def _count_unmatched_rows() -> int:
    async with SessionFactory() as session:
        return (
            await session.execute(
                text(f"SELECT COUNT(*) FROM {_MATCHES_TABLE} WHERE match_method = 'unmatched'")
            )
        ).scalar_one()


async def _delete_unmatched_rows() -> None:
    async with SessionFactory() as session:
        await session.execute(
            text(f"DELETE FROM {_MATCHES_TABLE} WHERE match_method = 'unmatched'")
        )
        await session.commit()


async def _current_alembic_version() -> str:
    async with SessionFactory() as session:
        return (
            await session.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one()


def test_downgrade_fails_closed_with_unmatched_rows_then_succeeds_after_cleanup() -> None:
    # Target the revision explicitly rather than a relative "-1": later
    # migrations may stack on top of 20260717_0025, and this test exercises
    # that specific migration's downgrade behavior regardless of how many
    # steps separate it from whatever the current head happens to be.
    config = _alembic_config()
    original_head = _run(_current_alembic_version())
    try:
        _run(_seed_unmatched_row())
        assert _run(_count_unmatched_rows()) >= 1

        with pytest.raises(RuntimeError, match=_REVISION):
            command.downgrade(config, _DOWN_REVISION)

        # The controlled failure must abort the whole downgrade batch, not
        # leave it partially applied -- alembic runs the full requested
        # range in one transaction by default, so a failure anywhere in it
        # must roll back to the version we started from.
        assert _run(_current_alembic_version()) == original_head

        _run(_delete_unmatched_rows())
        command.downgrade(config, _DOWN_REVISION)
        assert _run(_current_alembic_version()) == _DOWN_REVISION
    finally:
        command.upgrade(config, "head")
