"""HTML parser for Petmall Armenia product data."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from app.common.time import utc_now

logger = logging.getLogger(__name__)


@dataclass
class ParsedProduct:
    """Structured product data extracted from a page."""
    
    url: str
    title: str
    description: str | None
    price_amount: int
    currency_code: str
    stock_status: str
    weight_kg: float | None
    package_size: str | None
    image_url: str | None
    brand: str
    category: str | None
    sku: str | None
    collected_at: datetime
    source_page_url: str
    raw_data: dict[str, Any]


class PetmallAmParser:
    """Parses product data from Petmall Armenia HTML pages."""

    def __init__(self, source_page_url: str) -> None:
        self.source_page_url = source_page_url

    def parse_json_ld(self, html_content: str) -> ParsedProduct | None:
        """Extract structured data from JSON-LD script tags."""
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Look for JSON-LD script tags
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                
                # Handle both single product and array of products
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Product":
                            return self._extract_product_from_json_ld(item, html_content)
                elif data.get("@type") == "Product":
                    return self._extract_product_from_json_ld(data, html_content)
                    
            except (json.JSONDecodeError, AttributeError, KeyError) as exc:
                logger.debug("Failed to parse JSON-LD: %s", exc)
                continue
        
        return None

    def _extract_product_from_json_ld(
        self, data: dict[str, Any], html_content: str
    ) -> ParsedProduct:
        """Extract product fields from a JSON-LD Product object."""
        
        # Extract offers (price and availability)
        offers = data.get("offers", {})
        if isinstance(offers, list):
            offer = offers[0] if offers else {}
        else:
            offer = offers
        
        # Parse price
        price_str = offer.get("price", "0")
        try:
            price_amount = int(float(str(price_str).replace(",", "")))
        except (ValueError, TypeError):
            price_amount = 0
        
        currency_code = offer.get("priceCurrency", "AMD")
        
        # Parse availability
        availability_url = offer.get("availability", "")
        stock_status = self._parse_availability(availability_url)
        
        # Extract weight from description or name
        weight_kg = self._extract_weight(data.get("description", "") or data.get("name", ""))
        
        # Extract package size
        package_size = self._extract_package_size(
            data.get("description", "") or data.get("name", "")
        )
        
        # Get image URL
        image = data.get("image")
        if isinstance(image, list):
            image_url = image[0] if image else None
        elif isinstance(image, str):
            image_url = image
        else:
            image_url = None
        
        # Extract SKU if available
        sku = data.get("sku") or data.get("mpn") or data.get("productID")
        
        return ParsedProduct(
            url=data.get("url", self.source_page_url),
            title=data.get("name", ""),
            description=data.get("description"),
            price_amount=price_amount,
            currency_code=currency_code,
            stock_status=stock_status,
            weight_kg=weight_kg,
            package_size=package_size,
            image_url=image_url,
            brand=data.get("brand", {}).get("name", "Royal Canin"),
            category=data.get("category"),
            sku=sku,
            collected_at=utc_now(),
            source_page_url=self.source_page_url,
            raw_data={
                "json_ld": data,
                "extraction_method": "json_ld",
            },
        )

    def _parse_availability(self, availability_url: str) -> str:
        """Convert schema.org availability URL to our stock status."""
        if not availability_url:
            return "unknown"
        
        availability_lower = availability_url.lower()
        
        if "instock" in availability_lower:
            return "in_stock"
        elif "outofstock" in availability_lower or "discontinued" in availability_lower:
            return "out_of_stock"
        elif "preorder" in availability_lower or "backorder" in availability_lower:
            return "low_stock"
        
        return "unknown"

    def _extract_weight(self, text: str) -> float | None:
        """Extract weight in kg from text (e.g., '2 kg', '500 g')."""
        if not text:
            return None
        
        # Try to find weight patterns
        # kg pattern
        match = re.search(r"(\d+(?:\.\d+)?)\s*kg", text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        
        # g pattern (convert to kg)
        match = re.search(r"(\d+(?:\.\d+)?)\s*g\b", text, re.IGNORECASE)
        if match:
            grams = float(match.group(1))
            return grams / 1000.0
        
        return None

    def _extract_package_size(self, text: str) -> str | None:
        """Extract package size description from text."""
        if not text:
            return None
        
        # Look for common package size patterns
        patterns = [
            r"(\d+\s*x\s*\d+\s*g)",  # e.g., "12 x 85 g"
            r"(\d+\s*kg)",  # e.g., "2 kg"
            r"(\d+\s*l)",  # e.g., "1 l"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None

    def parse_listing_page(self, html_content: str) -> list[str]:
        """Extract product URLs from a brand listing page."""
        soup = BeautifulSoup(html_content, "html.parser")
        product_urls: list[str] = []
        
        # Look for product links (usually in product cards or list items)
        # Common patterns: /en/products/, /hy/products/, /ru/products/
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/products/" in href and href not in product_urls:
                # Normalize URL
                if href.startswith("/"):
                    href = "https://petmall.am" + href
                product_urls.append(href)
        
        logger.info("Extracted %d product URLs from listing page", len(product_urls))
        return product_urls

    def get_total_pages(self, html_content: str) -> int:
        """Extract total number of pages from pagination."""
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Look for pagination links
        pagination = soup.find("nav", class_="pagination") or soup.find("ul", class_="pagination")
        if not pagination:
            return 1
        
        # Find the highest page number
        max_page = 1
        for link in pagination.find_all("a", href=True):
            href = link["href"]
            # Look for page=N parameter
            match = re.search(r"[?&]page=(\d+)", href)
            if match:
                page_num = int(match.group(1))
                max_page = max(max_page, page_num)
        
        return max_page
