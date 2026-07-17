from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from app.db.session import SessionFactory
from app.integrations.price_intelligence.service import (
    ObservationIdentityConflict,
    PriceIntelligenceService,
)
from app.modules.price_intelligence.models import ExternalPriceObservation
from sqlalchemy import func, select, update


async def create_product() -> tuple[UUID, UUID, UUID]:
    async with SessionFactory() as session:
        service = PriceIntelligenceService(session)
        token = uuid4().hex
        source = await service.get_or_create_source(
            f"test-{token}",
            name="Test source",
            base_url="https://example.test",
            country_code="AM",
            default_currency="AMD",
        )
        seller = await service.get_or_create_seller(source.id, seller_name=f"seller-{token}")
        product, _ = await service.upsert_external_product(
            source.id,
            f"product-{token}",
            source_url=f"https://example.test/{token}",
            source_title="Test food",
            brand_name="Royal Canin",
            seller_id=seller.id,
        )
        await session.commit()
        return source.id, seller.id, product.id


def observation_args(
    seller_id: UUID, observed_at: datetime, price: int = 1000
) -> dict[str, object]:
    return {
        "seller_id": seller_id,
        "currency": "AMD",
        "currency_exponent": 0,
        "price_minor": price,
        "availability": "available",
        "observed_at": observed_at,
    }


@pytest.mark.asyncio
async def test_exact_replay_preserves_outer_transaction_and_remains_writable() -> None:
    source_id, seller_id, product_id = await create_product()
    observed_at = datetime.now(UTC)
    async with SessionFactory() as session:
        service = PriceIntelligenceService(session)
        run = await service.create_collection_run(source_id)
        first = await service.insert_observation(
            product_id, collection_run_id=run.id, **observation_args(seller_id, observed_at)
        )
        replay = await service.insert_observation(
            product_id, collection_run_id=run.id, **observation_args(seller_id, observed_at)
        )
        later = await service.insert_observation(
            product_id,
            collection_run_id=run.id,
            **observation_args(seller_id, observed_at + timedelta(microseconds=1)),
        )
        await session.commit()
        assert first.created is True
        assert replay.created is False
        assert later.created is True
        assert replay.observation.id == first.observation.id

    async with SessionFactory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(ExternalPriceObservation)
            .where(ExternalPriceObservation.external_product_id == product_id)
        )
        assert count == 2


@pytest.mark.asyncio
async def test_concurrent_exact_replay_creates_one_row() -> None:
    _source_id, seller_id, product_id = await create_product()
    observed_at = datetime.now(UTC)

    async def insert_once() -> bool:
        async with SessionFactory() as session:
            result = await PriceIntelligenceService(session).insert_observation(
                product_id, **observation_args(seller_id, observed_at)
            )
            await session.commit()
            return result.created

    assert sorted(await asyncio.gather(insert_once(), insert_once())) == [False, True]


@pytest.mark.asyncio
async def test_legacy_key_replays_and_identity_conflict_does_not_poison_session() -> None:
    _source_id, seller_id, product_id = await create_product()
    observed_at = datetime.now(UTC)
    async with SessionFactory() as session:
        service = PriceIntelligenceService(session)
        first = await service.insert_observation(
            product_id, **observation_args(seller_id, observed_at)
        )
        await session.execute(
            update(ExternalPriceObservation)
            .where(ExternalPriceObservation.id == first.observation.id)
            .values(ingestion_key="legacy-md5-key-" + uuid4().hex)
        )
        replay = await service.insert_observation(
            product_id, **observation_args(seller_id, observed_at)
        )
        assert replay.created is False
        with pytest.raises(ObservationIdentityConflict):
            await service.insert_observation(
                product_id, **observation_args(seller_id, observed_at, price=2000)
            )
        valid = await service.insert_observation(
            product_id,
            **observation_args(seller_id, observed_at + timedelta(microseconds=1), price=2000),
        )
        await session.commit()
        assert valid.created is True
