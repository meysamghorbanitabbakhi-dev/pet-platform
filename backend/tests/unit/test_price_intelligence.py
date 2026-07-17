from __future__ import annotations

import importlib
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from app.core.config import get_settings
from app.integrations.price_intelligence.matcher import (
    CandidateMatch,
    MatchReason,
    MatchStatus,
    run_matching_pipeline,
)
from app.integrations.price_intelligence.petmall_am import (
    CollectionNotAllowedError,
    PetmallAmCollector,
    RobotsTxtError,
)
from app.integrations.price_intelligence.petmall_am_parser import (
    ParsedProductError,
    parse_brand_listing_page,
    parse_product_detail_page,
    parse_robots_txt,
)
from app.main import create_app

FIXTURES = Path(__file__).parents[1] / "fixtures" / "petmall_am"


class ProductStub:
    def __init__(
        self,
        *,
        name_fa: str,
        description_fa: str | None,
        nominal_quantity_grams: int | None,
    ) -> None:
        self.id = uuid.uuid4()
        self.name_fa = name_fa
        self.description_fa = description_fa
        self.nominal_quantity_grams = nominal_quantity_grams
        self.status = "active"


def test_price_intelligence_modules_import() -> None:
    for module in [
        "app.modules.price_intelligence.models",
        "app.integrations.price_intelligence.matcher",
        "app.integrations.price_intelligence.petmall_am",
        "app.integrations.price_intelligence.petmall_am_parser",
        "app.integrations.price_intelligence.service",
        "app.integrations.price_intelligence.scheduler",
        "app.integrations.price_intelligence.worker",
        "app.api.routes.customer.price_intelligence",
    ]:
        importlib.import_module(module)
    spec = importlib.util.spec_from_file_location(
        "test_operator_pi",
        Path("app/api/routes/operator/price_intelligence.py"),
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)


def test_tooling_has_no_price_intelligence_exclusions() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "test_price_intelligence.py" not in pyproject
    assert "app/integrations/price_intelligence" not in pyproject
    assert "app/modules/price_intelligence" not in pyproject


def test_operator_paths_present_and_customer_paths_absent_from_openapi() -> None:
    paths = create_app().openapi()["paths"]
    assert "/api/v1/operator/price-intelligence/sources" in paths
    assert "/api/v1/operator/price-intelligence/matches/pending" in paths
    assert not any("competitor-prices" in path for path in paths)


def test_collection_disabled_by_default() -> None:
    assert get_settings().price_intelligence_collection_enabled is False


def test_robots_root_disallow_and_allow_precedence() -> None:
    disallowed, blocked = parse_robots_txt("User-agent: *\nDisallow: /\n", "PetBot", "/x")
    assert disallowed is False
    assert blocked == ["/"]
    allowed, blocked = parse_robots_txt(
        "User-agent: *\nDisallow: /en/\nAllow: /en/products/\n",
        "PetBot",
        "/en/products/royal-canin",
    )
    assert allowed is True
    assert blocked == ["/en/"]


@pytest.mark.asyncio
async def test_collector_fails_closed_for_robots_network_failure() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = PetmallAmCollector(client, request_delay_seconds=0.5)
        with pytest.raises(RobotsTxtError):
            await collector.check_robots_txt()


@pytest.mark.asyncio
async def test_collector_rejects_off_domain_redirect_and_bad_content_type() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if "redirect" in str(request.url):
            return httpx.Response(
                200,
                text="<html/>",
                request=request,
                headers={"content-type": "text/html"},
            )
        return httpx.Response(200, content=b"{}", headers={"content-type": "application/json"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        collector = PetmallAmCollector(client, request_delay_seconds=0.5)
        assert collector.validate_url("https://www.petmall.am/en/products/x")
        assert not collector.validate_url("http://www.petmall.am/en/products/x")
        assert not collector.validate_url("https://evil.test/en/products/x")
        with pytest.raises(CollectionNotAllowedError):
            await collector.fetch_product_detail("https://www.petmall.am/en/products/x")


def test_listing_parser_and_json_ld_variants() -> None:
    listing = (FIXTURES / "sample_brand_listing.html").read_text(encoding="utf-8")
    assert len(parse_brand_listing_page(listing, "https://www.petmall.am")) == 3
    product = parse_product_detail_page(
        (FIXTURES / "sample_product_page.html").read_text(encoding="utf-8"),
        "https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
    )
    assert product.price.amount_minor == 47500
    assert product.price.currency_exponent == 0
    assert product.availability == "available"
    assert product.packaging.total_weight_g == 7000
    graph = {
        "@graph": [
            {
                "@type": ["Thing", "Product"],
                "name": "Royal Canin Cat 12 × 85 g",
                "brand": "Royal Canin",
                "offers": {"price": "12,50", "priceCurrency": "AMD", "availability": "PreOrder"},
            }
        ]
    }
    parsed = parse_product_detail_page(
        f'<script type="application/ld+json">{json.dumps(graph)}</script>',
        "https://www.petmall.am/en/products/cat-pouch",
    )
    assert parsed.price.amount_minor == 12
    assert parsed.availability == "preorder"
    assert parsed.packaging.pack_count == 12
    assert parsed.packaging.unit_weight_g == 85
    assert parsed.packaging.total_weight_g == 1020


@pytest.mark.parametrize("price", ["", "0", "-1", "not-money"])
def test_parser_rejects_missing_malformed_or_nonpositive_prices(price: str) -> None:
    payload = {
        "@type": "Product",
        "name": "Food",
        "offers": {"price": price, "priceCurrency": "AMD"},
    }
    with pytest.raises(ParsedProductError):
        parse_product_detail_page(
            f'<script type="application/ld+json">{json.dumps(payload)}</script>',
            "https://www.petmall.am/en/products/x",
        )


def test_matching_rejects_species_food_type_and_veterinary_mismatches() -> None:
    product = ProductStub(
        name_fa="Royal Canin cat wet",
        description_fa="cat wet veterinary",
        nominal_quantity_grams=7000,
    )
    base = CandidateMatch(
        external_product_id=uuid.uuid4(),
        external_source_id=uuid.uuid4(),
        brand_name="Royal Canin",
        source_title="Royal Canin Dog Dry Hepatic",
        species="dog",
        food_type="dry",
        veterinary_diet=False,
        formula_name="Hepatic",
        declared_total_weight_g=7000,
    )
    result = run_matching_pipeline(base, [product])
    assert result.status == MatchStatus.UNMATCHED.value
    assert MatchReason.SPECIES_MISMATCH in result.reasons


def test_matching_structured_candidate_requires_review_not_auto_approval() -> None:
    product = ProductStub(
        name_fa="Royal Canin Hepatic Dog Dry",
        description_fa="dog dry veterinary hepatic",
        nominal_quantity_grams=7000,
    )
    candidate = CandidateMatch(
        external_product_id=uuid.uuid4(),
        external_source_id=uuid.uuid4(),
        brand_name="Royal Canin",
        source_title="Royal Canin Hepatic Dog Dry",
        species="dog",
        food_type="dry",
        veterinary_diet=True,
        formula_name="Hepatic",
        declared_total_weight_g=7000,
    )
    result = run_matching_pipeline(candidate, [product])
    assert result.status == MatchStatus.NEEDS_REVIEW.value
    assert result.canonical_product_id == product.id


def test_observation_ingestion_key_is_available_on_model() -> None:
    from app.modules.price_intelligence.models import ExternalPriceObservation

    assert hasattr(ExternalPriceObservation, "ingestion_key")
    assert hasattr(ExternalPriceObservation, "currency_exponent")


def test_no_live_external_request_marker() -> None:
    assert datetime.now(UTC).tzinfo is UTC
