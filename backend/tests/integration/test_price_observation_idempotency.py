from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.db.session import SessionFactory, close_database
from app.integrations.price_intelligence import worker as worker_module
from app.integrations.price_intelligence.petmall_am import CollectedPage, PetmallAmCollector
from app.integrations.price_intelligence.petmall_am_parser import (
    ParsedExternalProduct,
    ParsedPackaging,
    ParsedPrice,
    ParsedProductError,
)
from app.integrations.price_intelligence.service import (
    ObservationIdentityConflict,
    PriceIntelligenceService,
)
from app.integrations.price_intelligence.worker import run_petmall_am_collection
from app.modules.price_intelligence.models import (
    ExternalCollectionRun,
    ExternalPriceObservation,
)
from sqlalchemy import func, select, update


@pytest.fixture(autouse=True)
async def dispose_engine_between_event_loops() -> AsyncIterator[None]:
    """SessionFactory's engine binds to the event loop of the first connection
    it opens; pytest-asyncio gives each test function a fresh loop, so the
    engine must be disposed after every test or later tests reuse
    now-invalid connections from a closed loop."""
    yield
    await close_database()


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


@pytest.mark.asyncio
async def test_worker_counts_only_new_observations_and_preserves_partial_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The collection worker must not double-count duplicate observations, and a
    single product's parse failure must not discard the products collected
    around it in the same run."""
    token = uuid4().hex
    source_code = f"test-worker-{token}"
    monkeypatch.setattr(PetmallAmCollector, "SOURCE_CODE", source_code)

    async with SessionFactory() as session:
        service = PriceIntelligenceService(session)
        source = await service.get_or_create_source(
            source_code,
            name="Test worker source",
            base_url="https://example.test",
            country_code="AM",
            default_currency="AMD",
        )
        source.collection_enabled = True
        source.robots_status = "allowed"
        source.terms_status = "accepted"
        await session.commit()
        source_id = source.id

    collected_at = datetime.now(UTC)
    external_id = f"product-{token}"
    good_product = ParsedExternalProduct(
        external_product_id=external_id,
        url=f"https://example.test/{external_id}",
        title="Royal Canin Test Food",
        description=None,
        brand="Royal Canin",
        sku=None,
        image_url=None,
        availability="available",
        price=ParsedPrice(
            currency="AMD", currency_exponent=0, amount_minor=1000, raw_text="1000 AMD"
        ),
        packaging=ParsedPackaging(
            pack_count=None, unit_weight_g=None, total_weight_g=None, raw_text=None
        ),
        seller_name="Test seller",
        collected_at=collected_at,
        raw_data={},
    )
    urls = [
        f"https://example.test/{external_id}/ok-1",
        f"https://example.test/{external_id}/broken",
        f"https://example.test/{external_id}/ok-dup",
    ]

    async def fake_discover(self: PetmallAmCollector, page: int = 1) -> list[str]:
        return urls if page == 1 else []

    async def fake_fetch(self: PetmallAmCollector, product_url: str) -> CollectedPage:
        return CollectedPage(url=product_url, content="<html></html>", collected_at="")

    def fake_parse(content: str, url: str) -> ParsedExternalProduct:
        if "broken" in url:
            raise ParsedProductError("simulated parse failure")
        # Same natural identity (external_product_id + observed_at) both times,
        # so the second successful parse is a genuine duplicate, not a new row.
        return good_product

    monkeypatch.setattr(PetmallAmCollector, "discover_product_urls", fake_discover)
    monkeypatch.setattr(PetmallAmCollector, "fetch_product_detail", fake_fetch)
    monkeypatch.setattr(worker_module, "parse_product_detail_page", fake_parse)

    settings = get_settings()
    original_enabled = settings.price_intelligence_collection_enabled
    settings.price_intelligence_collection_enabled = True
    try:
        async with SessionFactory() as session:
            result = await run_petmall_am_collection(session, settings)
    finally:
        settings.price_intelligence_collection_enabled = original_enabled

    # A run that collected real products alongside a parse failure made
    # genuine progress -- it is "completed" (with errors_count still
    # reflecting the failure), not conflated with a run that collected
    # nothing at all.
    assert result["status"] == "completed"
    assert result["products"] == 2
    assert result["observations"] == 1

    async with SessionFactory() as session:
        run = await session.scalar(
            select(ExternalCollectionRun).where(
                ExternalCollectionRun.source_id == source_id
            )
        )
        assert run is not None
        assert run.products_seen == 2
        assert run.prices_inserted == 1
        assert run.errors_count == 1
        assert run.status == "completed"
        observation_count = await session.scalar(
            select(func.count())
            .select_from(ExternalPriceObservation)
            .where(ExternalPriceObservation.collection_run_id == run.id)
        )
        assert observation_count == 1


@pytest.mark.asyncio
async def test_worker_marks_run_failed_only_when_it_collected_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run that made zero real progress is genuinely "failed", distinct
    from the partial-success case above where some products were still
    collected around a parse failure."""
    token = uuid4().hex
    source_code = f"test-worker-{token}"
    monkeypatch.setattr(PetmallAmCollector, "SOURCE_CODE", source_code)

    async with SessionFactory() as session:
        service = PriceIntelligenceService(session)
        source = await service.get_or_create_source(
            source_code,
            name="Test worker source",
            base_url="https://example.test",
            country_code="AM",
            default_currency="AMD",
        )
        source.collection_enabled = True
        source.robots_status = "allowed"
        source.terms_status = "accepted"
        await session.commit()
        source_id = source.id

    urls = [f"https://example.test/{token}/broken-1", f"https://example.test/{token}/broken-2"]

    async def fake_discover(self: PetmallAmCollector, page: int = 1) -> list[str]:
        return urls if page == 1 else []

    async def fake_fetch(self: PetmallAmCollector, product_url: str) -> CollectedPage:
        return CollectedPage(url=product_url, content="<html></html>", collected_at="")

    def fake_parse(content: str, url: str) -> ParsedExternalProduct:
        raise ParsedProductError("simulated parse failure")

    monkeypatch.setattr(PetmallAmCollector, "discover_product_urls", fake_discover)
    monkeypatch.setattr(PetmallAmCollector, "fetch_product_detail", fake_fetch)
    monkeypatch.setattr(worker_module, "parse_product_detail_page", fake_parse)

    settings = get_settings()
    original_enabled = settings.price_intelligence_collection_enabled
    settings.price_intelligence_collection_enabled = True
    try:
        async with SessionFactory() as session:
            result = await run_petmall_am_collection(session, settings)
    finally:
        settings.price_intelligence_collection_enabled = original_enabled

    assert result["status"] == "failed"
    assert result["products"] == 0
    assert result["observations"] == 0

    async with SessionFactory() as session:
        run = await session.scalar(
            select(ExternalCollectionRun).where(
                ExternalCollectionRun.source_id == source_id
            )
        )
        assert run is not None
        assert run.products_seen == 0
        assert run.errors_count == 2
        assert run.status == "failed"
