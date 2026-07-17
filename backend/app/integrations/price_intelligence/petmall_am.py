"""Safe Petmall Armenia collector."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from app.common.time import utc_now
from app.core.config import Settings, get_settings
from app.integrations.price_intelligence.petmall_am_parser import (
    parse_brand_listing_page,
    parse_robots_txt,
)

ALLOWED_HOSTS = {"petmall.am", "www.petmall.am"}
HTML_TYPES = {"text/html", "application/xhtml+xml"}


class RobotsTxtError(Exception):
    """Robots policy cannot be safely verified."""


class CollectionNotAllowedError(Exception):
    """The requested collection is not policy-safe."""


@dataclass(frozen=True, slots=True)
class CollectedPage:
    url: str
    content: str
    collected_at: str


class PetmallAmCollector:
    SOURCE_CODE = "petmall_am"
    SOURCE_NAME = "Petmall Armenia"
    BASE_URL = "https://www.petmall.am"
    BRAND_URL = "https://www.petmall.am/en/pet-food/royal-canin"
    COUNTRY_CODE = "AM"
    CURRENCY_CODE = "AMD"

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        settings: Settings | None = None,
        user_agent: str | None = None,
        request_delay_seconds: float | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._http = http_client
        self._user_agent = user_agent or self._settings.price_intelligence_user_agent
        self._delay = (
            request_delay_seconds or self._settings.price_intelligence_request_delay_seconds
        )
        self._last_request_monotonic: float | None = None
        self._robots_txt: str | None = None

    async def check_robots_txt(
        self, path: str = "/en/pet-food/royal-canin"
    ) -> tuple[bool, str | None]:
        robots_url = f"{self.BASE_URL}/robots.txt"
        try:
            response = await self._request("GET", robots_url, check_robots=False)
        except Exception as exc:
            raise RobotsTxtError("robots_fetch_failed") from exc
        self._robots_txt = response.content
        allowed, blocked = parse_robots_txt(response.content, self._user_agent, path)
        return allowed, None if allowed else ",".join(blocked) or "disallowed"

    async def fetch_brand_page(self, page: int = 1) -> CollectedPage:
        params = f"?page={page}" if page > 1 else ""
        url = f"{self.BRAND_URL}{params}"
        await self._ensure_robots_allowed(url)
        return await self._request("GET", url)

    async def discover_product_urls(self, page: int = 1) -> list[str]:
        page_data = await self.fetch_brand_page(page)
        urls = parse_brand_listing_page(page_data.content, self.BASE_URL)
        return [url for url in urls if self.validate_url(url)]

    async def fetch_product_detail(self, product_url: str) -> CollectedPage:
        await self._ensure_robots_allowed(product_url)
        return await self._request("GET", product_url)

    def validate_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        if parsed.hostname not in ALLOWED_HOSTS:
            return False
        if parsed.username or parsed.password or parsed.fragment:
            return False
        if parsed.port not in (None, 443):
            return False
        return True

    async def _ensure_robots_allowed(self, url: str) -> None:
        if not self.validate_url(url):
            raise CollectionNotAllowedError("url_not_allowed")
        path = urlparse(url).path or "/"
        if self._robots_txt is None:
            allowed, _reason = await self.check_robots_txt(path)
        else:
            allowed, _blocked = parse_robots_txt(self._robots_txt, self._user_agent, path)
        if not allowed:
            raise CollectionNotAllowedError("robots_disallowed")

    async def _request(self, method: str, url: str, *, check_robots: bool = True) -> CollectedPage:
        if check_robots and not self.validate_url(url):
            raise CollectionNotAllowedError("url_not_allowed")
        await self._throttle()
        last_error: Exception | None = None
        for attempt in range(self._settings.price_intelligence_max_retries):
            try:
                response = await self._http.request(
                    method,
                    url,
                    headers={"User-Agent": self._user_agent},
                    follow_redirects=True,
                    timeout=self._settings.price_intelligence_timeout_seconds,
                )
                if not self.validate_url(str(response.url)):
                    raise CollectionNotAllowedError("redirect_not_allowed")
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if (
                    content_type
                    and content_type not in HTML_TYPES
                    and not url.endswith("/robots.txt")
                ):
                    raise CollectionNotAllowedError("unexpected_content_type")
                content = response.text
                if len(response.content) > self._settings.price_intelligence_max_response_bytes:
                    raise CollectionNotAllowedError("response_too_large")
                return CollectedPage(str(response.url), content, utc_now().isoformat())
            except (httpx.HTTPError, CollectionNotAllowedError) as exc:
                last_error = exc
                if isinstance(exc, CollectionNotAllowedError):
                    raise
                await asyncio.sleep(min(2**attempt, 8))
        raise RobotsTxtError("request_failed") from last_error

    async def _throttle(self) -> None:
        now = asyncio.get_running_loop().time()
        if self._last_request_monotonic is not None:
            elapsed = now - self._last_request_monotonic
            if elapsed < self._delay:
                await asyncio.sleep(self._delay - elapsed)
        self._last_request_monotonic = asyncio.get_running_loop().time()


def petmall_url(path: str) -> str:
    return urljoin(PetmallAmCollector.BASE_URL, path)
