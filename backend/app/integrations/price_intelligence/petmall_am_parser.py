"""Typed parser for Petmall Armenia pages."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urljoin

from app.common.time import utc_now

SOURCE_AVAILABILITY = {
    "instock": "available",
    "in stock": "available",
    "outofstock": "unavailable",
    "out of stock": "unavailable",
    "discontinued": "unavailable",
    "preorder": "preorder",
    "pre-order": "preorder",
    "backorder": "preorder",
}


class ParsedProductError(ValueError):
    """Raised when a page has no safe, persistable price observation."""


@dataclass(frozen=True, slots=True)
class ParsedPrice:
    currency: str
    currency_exponent: int
    amount_minor: int
    raw_text: str


@dataclass(frozen=True, slots=True)
class ParsedPackaging:
    pack_count: int | None
    unit_weight_g: int | None
    total_weight_g: int | None
    raw_text: str | None


@dataclass(frozen=True, slots=True)
class ParsedExternalProduct:
    external_product_id: str
    url: str
    title: str
    description: str | None
    brand: str
    sku: str | None
    image_url: str | None
    availability: str
    price: ParsedPrice
    packaging: ParsedPackaging
    seller_name: str | None
    collected_at: datetime
    raw_data: dict[str, Any]


def parse_robots_txt(content: str, user_agent: str, path: str) -> tuple[bool, list[str]]:
    """Evaluate robots.txt for a user agent and path using longest-match precedence."""
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    for raw_line in content.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        key = key.lower()
        if key == "user-agent":
            if agents and rules:
                groups.append((agents, rules))
                rules = []
            agents = [value.lower()]
        elif key in {"allow", "disallow"} and agents:
            rules.append((key, value))
    if agents:
        groups.append((agents, rules))

    ua = user_agent.lower()
    matched_rules: list[tuple[str, str]] = []
    for group_agents, group_rules in groups:
        if "*" in group_agents or any(agent and agent in ua for agent in group_agents):
            matched_rules.extend(group_rules)
    if not matched_rules:
        return True, []

    applicable = [(kind, rule) for kind, rule in matched_rules if rule and path.startswith(rule)]
    blocked = [rule for kind, rule in matched_rules if kind == "disallow" and rule]
    if not applicable:
        return True, blocked
    applicable.sort(key=lambda item: len(item[1]), reverse=True)
    return applicable[0][0] == "allow", blocked


def parse_brand_listing_page(
    html_content: str, base_url: str = "https://www.petmall.am"
) -> list[str]:
    urls: list[str] = []
    for match in re.finditer(r"""href\s*=\s*["'](?P<href>[^"']+)["']""", html_content, re.I):
        href = match.group("href")
        if "/products/" not in href:
            continue
        url = urljoin(base_url, href)
        if url not in urls:
            urls.append(url)
    return urls


def parse_product_detail_page(html_content: str, source_page_url: str) -> ParsedExternalProduct:
    for item in _json_ld_products(html_content):
        return _product_from_json_ld(item, source_page_url)
    raise ParsedProductError("json_ld_product_missing")


def _json_ld_products(html_content: str) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    pattern = re.compile(
        r"""<script[^>]+type=["']application/ld\+json["'][^>]*>(?P<body>.*?)</script>""",
        re.I | re.S,
    )
    for script in pattern.finditer(html_content):
        try:
            payload = json.loads(script.group("body").strip())
        except json.JSONDecodeError:
            continue
        products.extend(_walk_json_ld(payload))
    return products


def _walk_json_ld(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [product for item in payload for product in _walk_json_ld(item)]
    if not isinstance(payload, dict):
        return []
    graph = payload.get("@graph")
    if isinstance(graph, list):
        nested = [product for item in graph for product in _walk_json_ld(item)]
        if nested:
            return nested
    type_value = payload.get("@type")
    types = type_value if isinstance(type_value, list) else [type_value]
    return [payload] if "Product" in types else []


def _product_from_json_ld(data: dict[str, Any], source_page_url: str) -> ParsedExternalProduct:
    offer = _select_offer(data.get("offers"))
    raw_price = str(offer.get("price", "")).strip()
    price = _parse_price(raw_price, str(offer.get("priceCurrency", "AMD")).upper())
    text = " ".join(str(value or "") for value in (data.get("name"), data.get("description")))
    packaging = _parse_packaging(text)
    title = str(data.get("name") or "").strip()
    if not title:
        raise ParsedProductError("title_missing")
    sku = _optional_str(data.get("sku") or data.get("mpn") or data.get("productID"))
    return ParsedExternalProduct(
        external_product_id=sku or _slug_from_url(str(data.get("url") or source_page_url)),
        url=str(data.get("url") or source_page_url),
        title=title,
        description=_optional_str(data.get("description")),
        brand=_brand_name(data.get("brand")),
        sku=sku,
        image_url=_image_url(data.get("image")),
        availability=_parse_availability(_optional_str(offer.get("availability"))),
        price=price,
        packaging=packaging,
        seller_name=_seller_name(offer.get("seller")),
        collected_at=utc_now(),
        raw_data={"json_ld": data},
    )


def _select_offer(offers: Any) -> dict[str, Any]:
    if isinstance(offers, list):
        dicts = [offer for offer in offers if isinstance(offer, dict)]
        if not dicts:
            return {}
        return sorted(dicts, key=lambda item: str(item.get("price", "")))[0]
    return offers if isinstance(offers, dict) else {}


def _parse_price(raw_text: str, currency: str) -> ParsedPrice:
    normalized = raw_text.replace("\u00a0", "").replace(" ", "")
    if "," in normalized and "." not in normalized:
        normalized = normalized.replace(",", ".")
    else:
        normalized = normalized.replace(",", "")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise ParsedProductError("price_malformed") from exc
    if amount <= 0:
        raise ParsedProductError("price_not_positive")
    exponent = 0 if currency == "AMD" else 2
    minor = int((amount * (Decimal(10) ** exponent)).to_integral_value())
    return ParsedPrice(
        currency=currency,
        currency_exponent=exponent,
        amount_minor=minor,
        raw_text=raw_text,
    )


def _parse_availability(value: str | None) -> str:
    if not value:
        return "unknown"
    lowered = value.lower()
    for needle, mapped in SOURCE_AVAILABILITY.items():
        if needle in lowered:
            return mapped
    return "unknown"


def _parse_packaging(text: str) -> ParsedPackaging:
    multipack = re.search(
        r"(?P<count>\d+)\s*[x×]\s*(?P<unit>\d+(?:[\.,]\d+)?)\s*(?P<measure>kg|g)\b",
        text,
        re.IGNORECASE,
    )
    if multipack:
        count = int(multipack.group("count"))
        unit = _weight_to_grams(multipack.group("unit"), multipack.group("measure"))
        return ParsedPackaging(count, unit, count * unit, multipack.group(0))
    single = re.search(r"(?P<unit>\d+(?:[\.,]\d+)?)\s*(?P<measure>kg|g)\b", text, re.IGNORECASE)
    if single:
        unit = _weight_to_grams(single.group("unit"), single.group("measure"))
        return ParsedPackaging(1, unit, unit, single.group(0))
    return ParsedPackaging(None, None, None, None)


def _weight_to_grams(value: str, measure: str) -> int:
    amount = Decimal(value.replace(",", "."))
    if measure.lower() == "kg":
        amount *= Decimal(1000)
    return int(amount.to_integral_value())


def _brand_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "unknown")
    if isinstance(value, str):
        return value
    return "unknown"


def _image_url(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            return _optional_str(first.get("url"))
        return _optional_str(first)
    if isinstance(value, dict):
        return _optional_str(value.get("url"))
    return None


def _seller_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return _optional_str(value.get("name"))
    return _optional_str(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _slug_from_url(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1] or "unknown"
