from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
from app.db.session import SessionFactory, close_database
from app.main import create_app
from app.modules.catalog.models import Offer, Product, Supplier

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL is required",
)


@pytest.fixture(autouse=True)
async def dispose_engine_between_event_loops() -> AsyncIterator[None]:
    yield
    await close_database()


@dataclass(slots=True)
class SearchSeed:
    token: str
    available_offer_id: str
    unavailable_offer_id: str
    retired_offer_id: str


@pytest.fixture()
async def search_seed() -> SearchSeed:
    token = uuid.uuid4().hex[:10]
    async with SessionFactory() as session:
        supplier = Supplier(
            internal_name=f"search-supplier-{token}", country_code="IR", active=True
        )
        product = Product(name_fa="غذای جستجو", status="active")
        session.add_all([supplier, product])
        await session.flush()

        # Deliberately spelled with the Persian yeh/keh (ی/ک), matching what
        # real seeded catalog data uses -- the query side is what exercises
        # the Arabic-variant (ي/ك) normalization path.
        available = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"SRCH-{token}",
            title_fa=f"رویال کنین تست جستجو {token}",
            unit_label_fa="کیسه",
            price_irr=1_000_000,
            status="active",
            stock_posture="sourced_after_payment",
            sourcing_capacity_status="open",
            sourcing_route="individual",
            minimum_shelf_life_months=6,
        )
        unavailable = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"SRCH-UNAVAIL-{token}",
            title_fa=f"رویال کنین تست جستجو نامعتبر {token}",
            unit_label_fa="کیسه",
            price_irr=1_000_000,
            status="unavailable",
            stock_posture="unavailable",
            sourcing_capacity_status="open",
            sourcing_route="individual",
            minimum_shelf_life_months=6,
        )
        retired = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"SRCH-RETIRED-{token}",
            title_fa=f"رویال کنین تست جستجو بازنشسته {token}",
            unit_label_fa="کیسه",
            price_irr=1_000_000,
            status="retired",
            stock_posture="sourced_after_payment",
            sourcing_capacity_status="open",
            sourcing_route="individual",
            minimum_shelf_life_months=6,
        )
        session.add_all([available, unavailable, retired])
        await session.commit()
        return SearchSeed(
            token=token,
            available_offer_id=str(available.id),
            unavailable_offer_id=str(unavailable.id),
            retired_offer_id=str(retired.id),
        )


async def _search(client: httpx.AsyncClient, **params: object) -> httpx.Response:
    return await client.get("/api/v1/catalog/offers/search", params=params)


@pytest.fixture()
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_search_matches_arabic_spelled_query_against_persian_spelled_title(
    client: httpx.AsyncClient, search_seed: SearchSeed
) -> None:
    # Query uses Arabic yeh/kaf (ي/ك); the stored title uses Persian (ی/ک).
    # A naive substring match would miss this; normalization must not.
    arabic_query = f"رويال كنين تست جستجو {search_seed.token}"
    response = await _search(client, q=arabic_query)
    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert search_seed.available_offer_id in ids


async def test_search_matches_sku(client: httpx.AsyncClient, search_seed: SearchSeed) -> None:
    response = await _search(client, q=search_seed.token)
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert search_seed.available_offer_id in ids


async def test_search_excludes_unavailable_and_retired_offers(
    client: httpx.AsyncClient, search_seed: SearchSeed
) -> None:
    response = await _search(client, q=search_seed.token, limit=50)
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert search_seed.available_offer_id in ids
    assert search_seed.unavailable_offer_id not in ids
    assert search_seed.retired_offer_id not in ids


async def test_search_response_exposes_only_public_offer_fields(
    client: httpx.AsyncClient, search_seed: SearchSeed
) -> None:
    response = await _search(client, q=search_seed.token)
    item = response.json()["items"][0]
    assert set(item.keys()) == {
        "id",
        "product_id",
        "sku",
        "title_fa",
        "unit_label_fa",
        "price_irr",
        "reference_price_irr",
        "supplier_country",
        "stock_posture",
        "authenticity",
        "minimum_shelf_life_months",
        "reference_price_reviewed_at",
        "available_until",
    }


async def test_search_empty_result_has_typed_metadata_not_a_bare_list(
    client: httpx.AsyncClient,
) -> None:
    response = await _search(client, q="zzz-no-such-offer-anywhere-zzz")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["page"] == {"limit": 25, "offset": 0, "total": 0, "has_more": False}


async def test_search_requires_a_nonempty_query(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/catalog/offers/search")
    assert response.status_code == 422


async def test_search_whitespace_only_query_returns_typed_empty_result(
    client: httpx.AsyncClient,
) -> None:
    response = await _search(client, q="   ")
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_search_pagination_is_bounded_deterministic_and_non_overlapping(
    client: httpx.AsyncClient, search_seed: SearchSeed
) -> None:
    first = await _search(client, q="رویال کنین تست جستجو", limit=1, offset=0)
    second = await _search(client, q="رویال کنین تست جستجو", limit=1, offset=1)
    first_body, second_body = first.json(), second.json()
    assert first_body["page"]["limit"] == 1
    assert first_body["page"]["total"] >= 1
    if first_body["items"] and second_body["items"]:
        assert first_body["items"][0]["id"] != second_body["items"][0]["id"]

    over_limit = await _search(client, q="a", limit=1000)
    assert over_limit.status_code == 422  # bounded: Pagination caps limit at 100


async def test_search_ordering_is_deterministic_across_repeated_calls(
    client: httpx.AsyncClient, search_seed: SearchSeed
) -> None:
    first = await _search(client, q=search_seed.token, limit=50)
    second = await _search(client, q=search_seed.token, limit=50)
    first_ids = [item["id"] for item in first.json()["items"]]
    second_ids = [item["id"] for item in second.json()["items"]]
    assert first_ids == second_ids
    titles = [item["title_fa"] for item in first.json()["items"]]
    assert titles == sorted(titles)


async def test_search_like_metacharacters_in_query_are_treated_literally(
    client: httpx.AsyncClient,
) -> None:
    token = uuid.uuid4().hex[:8]
    async with SessionFactory() as session:
        supplier = Supplier(internal_name=f"esc-supplier-{token}", country_code="IR", active=True)
        product = Product(name_fa="محصول ویژه", status="active")
        session.add_all([supplier, product])
        await session.flush()
        offer = Offer(
            product_id=product.id,
            supplier_id=supplier.id,
            sku=f"ESC_{token}%50",
            title_fa=f"تخفیف ۵۰٪ محصول {token}",
            unit_label_fa="کیسه",
            price_irr=1_000_000,
            status="active",
            stock_posture="sourced_after_payment",
            sourcing_capacity_status="open",
            sourcing_route="individual",
            minimum_shelf_life_months=6,
        )
        session.add(offer)
        await session.commit()
        offer_id = str(offer.id)

    # A literal "_" and "%" in the query must match only that literal
    # character, not act as SQL LIKE wildcards over arbitrary offers.
    literal_match = await _search(client, q=f"ESC_{token}%50")
    assert offer_id in {item["id"] for item in literal_match.json()["items"]}

    wildcard_abuse = await _search(client, q=f"ESCX{token}X50")
    assert offer_id not in {item["id"] for item in wildcard_abuse.json()["items"]}
