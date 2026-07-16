"""Petmall Armenia price intelligence collector."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from app.common.time import utc_now
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RobotsTxtError(Exception):
    """Raised when robots.txt cannot be fetched or parsed."""


class CollectionNotAllowedError(Exception):
    """Raised when collection is not permitted for the target URL."""


class PetmallAmCollector:
    """Collects Royal Canin product data from petmall.am."""

    SOURCE_CODE = "petmall_am"
    SOURCE_NAME = "Petmall Armenia"
    BASE_URL = "https://petmall.am"
    ROYAL_CANIN_BRAND_URL = "https://petmall.am/en/pet-food/royal-canin"
    COUNTRY_CODE = "AM"
    CURRENCY_CODE = "AMD"

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        user_agent: str | None = None,
        request_delay_seconds: float = 2.0,
    ) -> None:
        settings = get_settings()
        self._http_client = http_client
        self._user_agent = user_agent or settings.price_intelligence_user_agent
        self._request_delay_seconds = (
            request_delay_seconds or settings.price_intelligence_request_delay_seconds
        )
        self._last_request_at: datetime | None = None
        self._robots_allowed: bool | None = None
        self._robots_txt_content: str | None = None

    async def check_robots_txt(self) -> bool:
        """Fetch and parse robots.txt to determine if collection is allowed."""
        robots_url = urljoin(self.BASE_URL, "/robots.txt")
        
        try:
            response = await self._http_client.get(
                robots_url,
                headers={"User-Agent": self._user_agent},
                follow_redirects=True,
            )
            response.raise_for_status()
            self._robots_txt_content = response.text
        except httpx.HTTPError as exc:
            logger.warning("Failed to fetch robots.txt from %s: %s", robots_url, exc)
            # Conservative: assume no access if robots.txt cannot be fetched
            self._robots_allowed = False
            raise RobotsTxtError(f"Failed to fetch robots.txt: {exc}") from exc

        self._robots_allowed = self._parse_robots_txt(self._robots_txt_content)
        logger.info(
            "Robots.txt check for %s: allowed=%s",
            self.SOURCE_CODE,
            self._robots_allowed,
        )
        return self._robots_allowed

    def _parse_robots_txt(self, content: str) -> bool:
        """Parse robots.txt and determine if our user agent is allowed."""
        lines = content.splitlines()
        
        # Simple robots.txt parser
        current_agent_matches = False
        disallow_paths: list[str] = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if line.lower().startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                current_agent_matches = agent == "*" or agent.lower() in self._user_agent.lower()
            
            elif current_agent_matches and line.lower().startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path:
                    disallow_paths.append(path)
        
        # Check if Royal Canin brand page is disallowed
        for path in disallow_paths:
            if self.ROYAL_CANIN_BRAND_URL.endswith(path):
                return False
        
        return True

    async def _throttle(self) -> None:
        """Enforce request delay to be polite to the source."""
        if self._last_request_at is not None:
            elapsed = (utc_now() - self._last_request_at).total_seconds()
            if elapsed < self._request_delay_seconds:
                await asyncio.sleep(self._request_delay_seconds - elapsed)
        self._last_request_at = utc_now()

    async def fetch_brand_page(self, page: int = 1) -> dict[str, Any]:
        """Fetch a single page of Royal Canin products from the brand listing."""
        if self._robots_allowed is None:
            await self.check_robots_txt()
        
        if not self._robots_allowed:
            raise CollectionNotAllowedError(
                f"Collection not allowed by robots.txt for {self.SOURCE_CODE}"
            )

        await self._throttle()

        url = self.ROYAL_CANIN_BRAND_URL
        params = {"page": page} if page > 1 else {}

        try:
            response = await self._http_client.get(
                url,
                params=params,
                headers={"User-Agent": self._user_agent},
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch brand page %d: %s", page, exc)
            raise

        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "content": response.text,
            "collected_at": utc_now().isoformat(),
        }

    async def fetch_product_detail(self, product_url: str) -> dict[str, Any]:
        """Fetch detailed product data from a product page."""
        if self._robots_allowed is False:
            raise CollectionNotAllowedError(f"Collection not allowed for {self.SOURCE_CODE}")

        await self._throttle()

        try:
            response = await self._http_client.get(
                product_url,
                headers={"User-Agent": self._user_agent},
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch product detail %s: %s", product_url, exc)
            raise

        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "content": response.text,
            "collected_at": utc_now().isoformat(),
        }

    async def discover_product_urls(self, page: int = 1) -> list[str]:
        """Discover product URLs from a brand listing page."""
        page_data = await self.fetch_brand_page(page)
        
        # Simple extraction: look for product links in the content
        # In production, this would use a proper HTML parser
        content = page_data["content"]
        product_urls: list[str] = []
        
        # Look for links to /en/products/ or /hy/products/ or /ru/products/
        for lang in ["en", "hy", "ru"]:
            prefix = f"/{lang}/products/"
            start = 0
            while True:
                idx = content.find(prefix, start)
                if idx == -1:
                    break
                # Find the end of the URL (quote or whitespace)
                end = idx
                while end < len(content) and content[end] not in ('"', "'", " ", ">", "<"):
                    end += 1
                url = urljoin(self.BASE_URL, content[idx:end])
                if url not in product_urls:
                    product_urls.append(url)
                start = end
        
        logger.info("Discovered %d product URLs on page %d", len(product_urls), page)
        return product_urls

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        # Caller manages the client lifecycle
        pass
