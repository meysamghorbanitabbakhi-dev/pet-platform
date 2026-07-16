"""Comprehensive tests for Petmall Armenia Price Intelligence Adapter."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, UTC
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.price_intelligence.matcher import (
    MatchMethod,
    MatchStatus,
    run_matching_pipeline,
    CandidateMatch,
)
from app.integrations.price_intelligence.petmall_am_parser import (
    parse_brand_listing_page,
    parse_product_detail_page,
    parse_robots_txt,
)
from app.integrations.price_intelligence.service import PriceIntelligenceService
from app.modules.catalog.models import Product, ProductSpecification
from app.modules.price_intelligence.models import (
    ExternalCollectionRun,
    ExternalPriceObservation,
    ExternalPriceSource,
    ExternalProduct,
    ExternalProductMatch,
    ExternalSeller,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "petmall_am"


@pytest.fixture
def sample_product_html():
    """Load sample product page HTML."""
    return (FIXTURES_DIR / "sample_product_page.html").read_text()


@pytest.fixture
def sample_brand_listing_html():
    """Load sample brand listing HTML."""
    return (FIXTURES_DIR / "sample_brand_listing.html").read_text()


@pytest.fixture
def robots_allowed_txt():
    """Load robots.txt that allows crawling."""
    return (FIXTURES_DIR / "robots_allowed.txt").read_text()


@pytest.fixture
def robots_disallowed_txt():
    """Load robots.txt that disallows crawling."""
    return (FIXTURES_DIR / "robots_disallowed.txt").read_text()


class TestRobotsTxtParsing:
    """Test robots.txt parsing."""

    def test_robots_allowed(self, robots_allowed_txt):
        """Test that allowed robots.txt permits product page crawling."""
        allowed, blocked_paths = parse_robots_txt(robots_allowed_txt)
        assert allowed is True
        assert "/en/products/" not in blocked_paths
        assert "/admin/" in blocked_paths

    def test_robots_disallowed(self, robots_disallowed_txt):
        """Test that disallowed robots.txt blocks all crawling."""
        allowed, blocked_paths = parse_robots_txt(robots_disallowed_txt)
        assert allowed is False
        assert "/" in blocked_paths


class TestProductPageParsing:
    """Test JSON-LD and HTML parsing."""

    def test_parse_product_detail_page(self, sample_product_html):
        """Test parsing JSON-LD from product detail page."""
        parsed = parse_product_detail_page(sample_product_html)
        
        assert parsed is not None
        assert parsed["name"] == "Royal Canin Veterinary Diet Hepatic Dog Food"
        assert parsed["sku"] == "RC-HEP-7KG"
        assert parsed["brand"]["name"] == "Royal Canin"
        assert parsed["offers"]["price"] == "47500"
        assert parsed["offers"]["priceCurrency"] == "AMD"
        assert parsed["offers"]["availability"] == "https://schema.org/InStock"
        assert parsed["offers"]["seller"]["name"] == "RoCan Store"
        
        # Check weight parsing
        assert parsed["weight"]["value"] == "7"
        assert parsed["weight"]["unitCode"] == "kg"

    def test_parse_product_missing_json_ld(self):
        """Test handling of pages without JSON-LD."""
        html = "<html><body><h1>No JSON-LD here</h1></body></html>"
        parsed = parse_product_detail_page(html)
        assert parsed is None


class TestBrandListingParsing:
    """Test brand listing page parsing."""

    def test_parse_brand_listing_page(self, sample_brand_listing_html):
        """Test extracting product URLs from brand listing."""
        product_urls = parse_brand_listing_page(sample_brand_listing_html)
        
        assert len(product_urls) == 3
        assert "https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg" in product_urls
        assert "https://www.petmall.am/en/products/royal-canin-kitten-2kg" in product_urls
        assert "https://www.petmall.am/en/products/royal-canin-adult-dog-15kg" in product_urls

    def test_parse_brand_listing_empty(self):
        """Test handling of empty brand listing."""
        html = "<html><body><h1>No products</h1></body></html>"
        product_urls = parse_brand_listing_page(html)
        assert len(product_urls) == 0


class TestExternalProductManagement:
    """Test external product upsert and management."""

    @pytest.mark.asyncio
    async def test_upsert_external_product_created(
        self, session: AsyncSession
    ):
        """Test creating new external product."""
        service = PriceIntelligenceService(session)
        
        # Get source
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        # Create external product
        ext_product = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            product_line="Veterinary Diet",
            formula_name="Hepatic",
            species="dog",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,
            declared_total_weight_g=7000,
            availability="in_stock",
            seller_name="RoCan Store",
        )
        
        await session.commit()
        
        assert ext_product is not None
        assert ext_product.external_product_id == "RC-HEP-7KG"
        assert ext_product.species == "dog"
        assert ext_product.veterinary_diet is True
        assert ext_product.declared_total_weight_g == 7000

    @pytest.mark.asyncio
    async def test_upsert_external_product_idempotent(
        self, session: AsyncSession
    ):
        """Test that upsert is idempotent."""
        service = PriceIntelligenceService(session)
        
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        # Create product
        ext_product1 = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
        )
        await session.commit()
        
        # Upsert same product
        ext_product2 = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food 7kg",  # Updated title
            brand_name="Royal Canin",
        )
        await session.commit()
        
        # Should be same record
        assert ext_product1["id"] == ext_product2["id"]
        assert ext_product2["source_title"] == "Royal Canin Hepatic Dog Food 7kg"


class TestPriceObservations:
    """Test price observation insertion."""

    @pytest.mark.asyncio
    async def test_insert_observation(self, session: AsyncSession):
        """Test inserting price observation."""
        service = PriceIntelligenceService(session)
        
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        ext_product = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
        )
        await session.commit()
        
        obs = await service.insert_observation(
            external_product_id=ext_product["id"],
            seller_id=ext_product["seller_id"],
            currency="AMD",
            price_minor=4750000,  # 47500 AMD = 4750000 luma (100 luma = 1 AMD)
            compare_at_price_minor=5200000,
            observed_at=datetime.now(UTC),
            availability="in_stock",
        )
        await session.commit()
        
        assert obs is not None
        assert obs["price_minor"] == 4750000
        assert obs["currency"] == "AMD"
        # AMD exponent is 0, so unit_price_per_kg_minor = price_minor
        # 4750000 / 7000g * 1000 = 678571 luma/kg
        assert obs["unit_price_per_kg_minor"] == 678571

    @pytest.mark.asyncio
    async def test_observation_idempotency(self, session: AsyncSession):
        """Test that duplicate observations are not inserted."""
        service = PriceIntelligenceService(session)
        
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        ext_product = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
        )
        await session.commit()
        
        observed_at = datetime.now(UTC)
        
        # Insert first observation
        obs1 = await service.insert_observation(
            external_product_id=ext_product["id"],
            seller_id=ext_product["seller_id"],
            currency="AMD",
            price_minor=4750000,
            observed_at=observed_at,
            availability="in_stock",
        )
        await session.commit()
        
        # Insert duplicate
        obs2 = await service.insert_observation(
            external_product_id=ext_product["id"],
            seller_id=ext_product["seller_id"],
            currency="AMD",
            price_minor=4750000,
            observed_at=observed_at,
            availability="in_stock",
        )
        
        # Should return first observation, not create new
        assert obs1["id"] == obs2["id"]


class TestProductMatching:
    """Test product matching logic with mandatory protections."""

    @pytest.mark.asyncio
    async def test_ean_exact_match_auto_approvers(
        self, session: AsyncSession
    ):
        """Test that EAN exact match auto-approvers."""
        service = PriceIntelligenceService(session)
        
        # Create canonical product with EAN
        product = Product(
            name="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            product_line="Veterinary Diet",
            formula_name="Hepatic",
            status="active",
        )
        session.add(product)
        await session.flush()
        
        spec = ProductSpecification(
            product_id=product.id,
            species="dog",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,
            weight_g=7000,
            ean="1234567890123",
        )
        session.add(spec)
        await session.commit()
        
        # Create external product with same EAN
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        ext_product = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            declared_ean="1234567890123",
        )
        await session.commit()
        
        # Run matching
        match_result = await service.run_match_for_product(ext_product["id"])
        await session.commit()
        
        # Should auto-approve
        assert match_result["match_status"] == MatchStatus.APPROVED.value
        assert match_result["match_method"] == MatchMethod.EAN_EXACT.value
        assert match_result["canonical_product_id"] == str(product.id)

    @pytest.mark.asyncio
    async def test_formula_weight_match_requires_review(
        self, session: AsyncSession
    ):
        """Test that formula+weight match requires review."""
        service = PriceIntelligenceService(session)
        
        # Create canonical product without EAN
        product = Product(
            name="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            product_line="Veterinary Diet",
            formula_name="Hepatic",
            status="active",
        )
        session.add(product)
        await session.flush()
        
        spec = ProductSpecification(
            product_id=product.id,
            species="dog",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,
            weight_g=7000,
        )
        session.add(spec)
        await session.commit()
        
        # Create external product without EAN but matching attributes
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        ext_product = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            product_line="Veterinary Diet",
            formula_name="Hepatic",
            species="dog",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,
            declared_total_weight_g=7000,
        )
        await session.commit()
        
        # Run matching
        match_result = await service.run_match_for_product(ext_product["id"])
        await session.commit()
        
        # Should require review
        assert match_result["match_status"] == MatchStatus.NEEDS_REVIEW.value
        assert match_result["match_method"] == MatchMethod.EXACT_FORMULA_WEIGHT.value
        assert match_result["canonical_product_id"] == str(product.id)
        assert len(match_result["match_reasons"]) > 0

    @pytest.mark.asyncio
    async def test_species_mismatch_rejected(self, session: AsyncSession):
        """Test that species mismatch is rejected."""
        service = PriceIntelligenceService(session)
        
        # Create canonical product for cat
        product = Product(
            name="Royal Canin Hepatic Cat Food",
            brand_name="Royal Canin",
            product_line="Veterinary Diet",
            formula_name="Hepatic",
            status="active",
        )
        session.add(product)
        await session.flush()
        
        spec = ProductSpecification(
            product_id=product.id,
            species="cat",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,
            weight_g=7000,
        )
        session.add(spec)
        await session.commit()
        
        # Create external product for dog
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        ext_product = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            product_line="Veterinary Diet",
            formula_name="Hepatic",
            species="dog",  # Dog, not cat
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,
            declared_total_weight_g=7000,
        )
        await session.commit()
        
        # Run matching
        match_result = await service.run_match_for_product(ext_product["id"])
        await session.commit()
        
        # Should be rejected due to species mismatch
        assert match_result["match_status"] == MatchStatus.REJECTED.value
        assert "species mismatch" in match_result["match_reasons"]

    @pytest.mark.asyncio
    async def test_wet_dry_mismatch_rejected(self, session: AsyncSession):
        """Test that wet/dry food type mismatch is rejected."""
        service = PriceIntelligenceService(session)
        
        # Create canonical product (wet food)
        product = Product(
            name="Royal Canin Hepatic Dog Food Wet",
            brand_name="Royal Canin",
            product_line="Veterinary Diet",
            formula_name="Hepatic",
            status="active",
        )
        session.add(product)
        await session.flush()
        
        spec = ProductSpecification(
            product_id=product.id,
            species="dog",
            food_type="wet",
            life_stage="adult",
            veterinary_diet=True,
            weight_g=7000,
        )
        session.add(spec)
        await session.commit()
        
        # Create external product (dry food)
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        ext_product = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            product_line="Veterinary Diet",
            formula_name="Hepatic",
            species="dog",
            food_type="dry",  # Dry, not wet
            life_stage="adult",
            veterinary_diet=True,
            declared_total_weight_g=7000,
        )
        await session.commit()
        
        # Run matching
        match_result = await service.run_match_for_product(ext_product["id"])
        await session.commit()
        
        # Should be rejected due to food type mismatch
        assert match_result["match_status"] == MatchStatus.REJECTED.value
        assert "food type mismatch" in match_result["match_reasons"]

    @pytest.mark.asyncio
    async def test_veterinary_diet_mismatch_rejected(
        self, session: AsyncSession
    ):
        """Test that veterinary/retail mismatch is rejected."""
        service = PriceIntelligenceService(session)
        
        # Create canonical retail product
        product = Product(
            name="Royal Canin Adult Dog Food",
            brand_name="Royal Canin",
            product_line="Size Health Nutrition",
            formula_name="Medium Adult",
            status="active",
        )
        session.add(product)
        await session.flush()
        
        spec = ProductSpecification(
            product_id=product.id,
            species="dog",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=False,  # Retail
            weight_g=7000,
        )
        session.add(spec)
        await session.commit()
        
        # Create external veterinary product
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        ext_product = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            product_line="Veterinary Diet",
            formula_name="Hepatic",
            species="dog",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,  # Veterinary
            declared_total_weight_g=7000,
        )
        await session.commit()
        
        # Run matching
        match_result = await service.run_match_for_product(ext_product["id"])
        await session.commit()
        
        # Should be rejected due to veterinary/retail mismatch
        assert match_result["match_status"] == MatchStatus.REJECTED.value
        assert "veterinary/retail mismatch" in match_result["match_reasons"]

    @pytest.mark.asyncio
    async def test_no_match_when_catalog_empty(self, session: AsyncSession):
        """Test that no match is suggested when catalog is empty."""
        service = PriceIntelligenceService(session)
        
        # Create external product but no canonical products
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        ext_product = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            species="dog",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,
            declared_total_weight_g=7000,
        )
        await session.commit()
        
        # Run matching
        match_result = await service.run_match_for_product(ext_product["id"])
        await session.commit()
        
        # Should not match
        assert match_result["match_status"] == MatchStatus.NO_MATCH.value
        assert match_result["canonical_product_id"] is None


class TestCollectionRuns:
    """Test collection run tracking."""

    @pytest.mark.asyncio
    async def test_create_collection_run(self, session: AsyncSession):
        """Test creating a collection run."""
        service = PriceIntelligenceService(session)
        
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        run = await service.create_collection_run(
            source_id=source.id,
            max_pages=10,
        )
        await session.commit()
        
        assert run is not None
        assert run["status"] == "running"
        assert run["max_pages"] == 10

    @pytest.mark.asyncio
    async def test_complete_collection_run(self, session: AsyncSession):
        """Test completing a collection run."""
        service = PriceIntelligenceService(session)
        
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        run = await service.create_collection_run(
            source_id=source.id,
            max_pages=10,
        )
        await session.commit()
        
        # Complete run
        await service.complete_collection_run(
            run_id=run["id"],
            products_seen=50,
            products_created=45,
            products_updated=5,
            prices_inserted=50,
            pages_succeeded=10,
            warnings_count=2,
            errors_count=0,
        )
        await session.commit()
        
        # Verify completion
        completed_run = await service.get_collection_run(run["id"])
        assert completed_run["status"] == "completed"
        assert completed_run["products_seen"] == 50
        assert completed_run["prices_inserted"] == 50


class TestManualApprovalRejection:
    """Test manual match approval and rejection."""

    @pytest.mark.asyncio
    async def test_approve_match(self, session: AsyncSession):
        """Test manual approval of a match."""
        service = PriceIntelligenceService(session)
        
        # Create canonical product
        product = Product(
            name="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            product_line="Veterinary Diet",
            formula_name="Hepatic",
            status="active",
        )
        session.add(product)
        await session.flush()
        
        spec = ProductSpecification(
            product_id=product.id,
            species="dog",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,
            weight_g=7000,
        )
        session.add(spec)
        await session.commit()
        
        # Create external product
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        ext_product = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            species="dog",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,
            declared_total_weight_g=7000,
        )
        await session.commit()
        
        # Run matching (should require review)
        match_result = await service.run_match_for_product(ext_product["id"])
        await session.commit()
        
        assert match_result["match_status"] == MatchStatus.NEEDS_REVIEW.value
        
        # Manually approve
        approved = await service.approve_match(
            match_id=match_result["id"],
            reviewed_by=uuid.uuid4(),  # Mock operator ID
        )
        await session.commit()
        
        assert approved["match_status"] == MatchStatus.APPROVED.value

    @pytest.mark.asyncio
    async def test_reject_match(self, session: AsyncSession):
        """Test manual rejection of a match."""
        service = PriceIntelligenceService(session)
        
        # Create canonical product
        product = Product(
            name="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            product_line="Veterinary Diet",
            formula_name="Hepatic",
            status="active",
        )
        session.add(product)
        await session.flush()
        
        spec = ProductSpecification(
            product_id=product.id,
            species="dog",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,
            weight_g=7000,
        )
        session.add(spec)
        await session.commit()
        
        # Create external product
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        ext_product = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            species="dog",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,
            declared_total_weight_g=7000,
        )
        await session.commit()
        
        # Run matching
        match_result = await service.run_match_for_product(ext_product["id"])
        await session.commit()
        
        # Manually reject
        rejected = await service.reject_match(
            match_id=match_result["id"],
            reviewed_by=uuid.uuid4(),  # Mock operator ID
        )
        await session.commit()
        
        assert rejected["match_status"] == MatchStatus.REJECTED.value


class TestQueryHelpers:
    """Test query helper methods."""

    @pytest.mark.asyncio
    async def test_list_pending_matches(self, session: AsyncSession):
        """Test listing pending matches."""
        service = PriceIntelligenceService(session)
        
        # Create canonical product
        product = Product(
            name="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            product_line="Veterinary Diet",
            formula_name="Hepatic",
            status="active",
        )
        session.add(product)
        await session.flush()
        
        spec = ProductSpecification(
            product_id=product.id,
            species="dog",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,
            weight_g=7000,
        )
        session.add(spec)
        await session.commit()
        
        # Create external product
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        ext_product = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
            species="dog",
            food_type="dry",
            life_stage="adult",
            veterinary_diet=True,
            declared_total_weight_g=7000,
        )
        await session.commit()
        
        # Run matching (should require review)
        await service.run_match_for_product(ext_product["id"])
        await session.commit()
        
        # List pending matches
        pending = await service.list_pending_matches(limit=10)
        
        assert len(pending) == 1
        assert pending[0]["match_status"] == MatchStatus.NEEDS_REVIEW.value

    @pytest.mark.asyncio
    async def test_get_product_price_history(self, session: AsyncSession):
        """Test getting product price history."""
        service = PriceIntelligenceService(session)
        
        source = await service.get_or_create_source(
            code="petmall_am",
            name="Petmall Armenia",
            base_url="https://www.petmall.am",
            country_code="AM",
            default_currency="AMD",
        )
        
        ext_product = await service.upsert_external_product(
            source_id=source.id,
            external_product_id="RC-HEP-7KG",
            source_url="https://www.petmall.am/en/products/royal-canin-hepatic-dog-7kg",
            source_title="Royal Canin Hepatic Dog Food",
            brand_name="Royal Canin",
        )
        await session.commit()
        
        # Insert multiple observations
        from datetime import timedelta
        
        base_time = datetime.now(UTC)
        for i in range(3):
            observed_at = base_time - timedelta(days=i)
            await service.insert_observation(
                external_product_id=ext_product["id"],
                seller_id=ext_product["seller_id"],
                currency="AMD",
                price_minor=4750000 + (i * 10000),  # Price varies
                observed_at=observed_at,
                availability="in_stock",
            )
        await session.commit()
        
        # Get price history
        history = await service.get_product_price_history(ext_product["id"])
        
        assert len(history) == 3
        # Should be ordered by observed_at descending (newest first)
        assert history[0]["observed_at"] > history[1]["observed_at"]
        assert history[1]["observed_at"] > history[2]["observed_at"]
