"""SKU matcher for price intelligence products."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of attempting to match an external product to our catalog."""
    
    matched: bool
    catalog_product_id: UUID | None
    catalog_sku: str | None
    confidence_score: float  # 0.0 to 1.0
    match_reason: str | None


class SKUMatcher:
    """Matches external price intelligence products to our catalog."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def match_product(
        self,
        external_title: str,
        external_sku: str | None,
        weight_kg: float | None,
        package_size: str | None,
        brand: str,
    ) -> MatchResult:
        """
        Attempt to match an external product to our catalog.
        
        Matching strategies (in order of priority):
        1. Exact SKU match (if external SKU is provided)
        2. Title similarity + weight/package match
        3. Weight + package size match only (low confidence)
        """
        
        # Strategy 1: Exact SKU match
        if external_sku:
            result = await self._match_by_sku(external_sku)
            if result.matched:
                logger.debug("Exact SKU match for %s", external_sku)
                return result

        # Strategy 2: Title + weight match
        result = await self._match_by_title_and_weight(
            external_title, weight_kg, package_size, brand
        )
        if result.matched and result.confidence_score >= 0.7:
            logger.debug("Title+weight match with confidence %.2f", result.confidence_score)
            return result

        # Strategy 3: Weight + package only (low confidence)
        if result.matched:
            logger.debug("Low confidence match (weight/package only)")
            return result

        # No match found
        return MatchResult(
            matched=False,
            catalog_product_id=None,
            catalog_sku=None,
            confidence_score=0.0,
            match_reason=None,
        )

    async def _match_by_sku(self, external_sku: str) -> MatchResult:
        """Try to match by exact SKU."""
        query = select(Product).where(Product.name_fa.ilike(f"%{external_sku}%"))
        result = await self._session.execute(query)
        product = result.scalar_one_or_none()

        if product:
            return MatchResult(
                matched=True,
                catalog_product_id=product.id,
                catalog_sku=None,
                confidence_score=1.0,
                match_reason=f"Exact SKU match: {external_sku}",
            )

        return MatchResult(
            matched=False,
            catalog_product_id=None,
            catalog_sku=None,
            confidence_score=0.0,
            match_reason=None,
        )

    async def _match_by_title_and_weight(
        self,
        external_title: str,
        weight_kg: float | None,
        package_size: str | None,
        brand: str,
    ) -> MatchResult:
        """Try to match by title similarity and weight/package size."""
        
        # Normalize external title for comparison
        normalized_title = self._normalize_title(external_title)
        
        # Fetch all Royal Canin products
        query = select(Product).where(Product.description_fa.ilike("%Royal Canin%"))
        result = await self._session.execute(query)
        products = result.scalars().all()

        best_match: MatchResult = MatchResult(
            matched=False,
            catalog_product_id=None,
            catalog_sku=None,
            confidence_score=0.0,
            match_reason=None,
        )

        for product in products:
            product_title = self._normalize_title(product.name_fa or "")
            
            # Calculate title similarity (simple Jaccard similarity on words)
            similarity = self._calculate_similarity(normalized_title, product_title)
            
            # Check weight match
            weight_match = False
            product_weight_kg = (
                product.nominal_quantity_grams / 1000
                if product.nominal_quantity_grams is not None
                else None
            )
            if weight_kg is not None and product_weight_kg is not None:
                weight_match = abs(weight_kg - product_weight_kg) < 0.01  # within 10g
            
            # Check package size match
            package_match = False
            product_package_size = (
                f"{product.nominal_quantity_grams}g"
                if product.nominal_quantity_grams is not None
                else None
            )
            if package_size and product_package_size:
                package_match = package_size.lower() == product_package_size.lower()
            
            # Calculate confidence score
            confidence = 0.0
            
            if similarity > 0.6:
                confidence += similarity * 0.5
            
            if weight_match:
                confidence += 0.3
            
            if package_match:
                confidence += 0.2
            
            if brand.lower() in (product.description_fa or "").lower():
                confidence += 0.1
            
            confidence = min(confidence, 1.0)
            
            # Update best match if this is better
            if confidence > best_match.confidence_score:
                reasons = []
                if similarity > 0.6:
                    reasons.append(f"title similarity: {similarity:.2f}")
                if weight_match:
                    reasons.append("weight match")
                if package_match:
                    reasons.append("package match")
                if brand.lower() in (product.description_fa or "").lower():
                    reasons.append("brand match")
                
                best_match = MatchResult(
                    matched=confidence >= 0.4,  # Minimum threshold
                    catalog_product_id=product.id,
                    catalog_sku=None,
                    confidence_score=confidence,
                    match_reason=", ".join(reasons) if reasons else None,
                )

        return best_match

    def _normalize_title(self, title: str) -> str:
        """Normalize product title for comparison."""
        import re
        
        # Convert to lowercase
        title = title.lower()
        
        # Remove special characters and extra whitespace
        title = re.sub(r"[^\w\s]", " ", title)
        title = re.sub(r"\s+", " ", title)
        
        # Remove common filler words
        stop_words = {"royal", "canin", "dog", "cat", "food", "dry", "wet", "for", "the", "a", "an"}
        words = [w for w in title.split() if w not in stop_words]
        
        return " ".join(words)

    def _calculate_similarity(self, title1: str, title2: str) -> float:
        """Calculate Jaccard similarity between two titles."""
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
