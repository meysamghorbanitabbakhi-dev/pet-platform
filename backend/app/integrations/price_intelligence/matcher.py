"""Fail-safe matching for external price-intelligence products."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class MatchMethod(StrEnum):
    UNMATCHED = "unmatched"
    EAN = "ean"
    EXACT_FORMULA_WEIGHT = "exact_formula_weight"
    NORMALIZED_ATTRIBUTES = "normalized_attributes"
    MANUAL = "manual"


class MatchStatus(StrEnum):
    UNMATCHED = "unmatched"
    SUGGESTED = "suggested"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class MatchReason(StrEnum):
    EXACT_EAN = "exact_ean"
    EXACT_SKU = "exact_sku"
    FORMULA_WEIGHT = "formula_weight"
    INSUFFICIENT_CANONICAL_DATA = "insufficient_canonical_data"
    SPECIES_MISMATCH = "species_mismatch"
    FOOD_TYPE_MISMATCH = "food_type_mismatch"
    VETERINARY_DIET_MISMATCH = "veterinary_diet_mismatch"
    PACKAGE_MISMATCH = "package_mismatch"


class CanonicalProduct(Protocol):
    id: UUID
    name_fa: str
    description_fa: str | None
    nominal_quantity_grams: int | None
    status: str


@dataclass(slots=True)
class CandidateMatch:
    external_product_id: UUID
    external_source_id: UUID
    brand_name: str
    source_title: str
    external_sku: str | None = None
    external_ean: str | None = None
    species: str | None = None
    food_type: str | None = None
    life_stage: str | None = None
    product_line: str | None = None
    formula_name: str | None = None
    veterinary_diet: bool | None = None
    declared_pack_count: int | None = None
    declared_unit_weight_g: int | None = None
    declared_total_weight_g: int | None = None


@dataclass(slots=True)
class MatchResult:
    status: str
    method: MatchMethod
    confidence: float
    canonical_product_id: UUID | None = None
    canonical_variant_id: UUID | None = None
    canonical_ean: str | None = None
    reasons: list[MatchReason] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def run_matching_pipeline(
    candidate: CandidateMatch,
    canonical_products: Sequence[CanonicalProduct],
) -> MatchResult:
    """Return an approved exact match, review candidate, or fail-safe unmatched result."""
    compatible: list[CanonicalProduct] = []
    mismatch_reasons: set[MatchReason] = set()
    for product in canonical_products:
        reason = _hard_mismatch(candidate, product)
        if reason is not None:
            mismatch_reasons.add(reason)
            continue
        compatible.append(product)

    if not compatible:
        return MatchResult(
            status=MatchStatus.UNMATCHED.value,
            method=MatchMethod.UNMATCHED,
            confidence=0.0,
            reasons=sorted(mismatch_reasons, key=lambda item: item.value),
        )

    if candidate.external_ean:
        # The current K9 catalog has no EAN column. Leave the boundary explicit.
        return MatchResult(
            status=MatchStatus.NEEDS_REVIEW.value,
            method=MatchMethod.EAN,
            confidence=0.5,
            reasons=[MatchReason.INSUFFICIENT_CANONICAL_DATA],
            warnings=["canonical_ean_absent"],
        )

    structured = [
        product
        for product in compatible
        if candidate.declared_total_weight_g
        and product.nominal_quantity_grams == candidate.declared_total_weight_g
        and _text_contains(product, candidate.formula_name)
    ]
    if len(structured) == 1:
        return MatchResult(
            status=MatchStatus.NEEDS_REVIEW.value,
            method=MatchMethod.EXACT_FORMULA_WEIGHT,
            confidence=0.8,
            canonical_product_id=structured[0].id,
            reasons=[MatchReason.FORMULA_WEIGHT],
        )

    if candidate.external_sku:
        # Canonical product SKU semantics are not present on Product. Do not infer.
        return MatchResult(
            status=MatchStatus.NEEDS_REVIEW.value,
            method=MatchMethod.NORMALIZED_ATTRIBUTES,
            confidence=0.4,
            reasons=[MatchReason.INSUFFICIENT_CANONICAL_DATA],
            warnings=["canonical_sku_semantics_absent"],
        )

    return MatchResult(
        status=MatchStatus.UNMATCHED.value,
        method=MatchMethod.UNMATCHED,
        confidence=0.0,
        reasons=[MatchReason.INSUFFICIENT_CANONICAL_DATA],
    )


def _hard_mismatch(candidate: CandidateMatch, product: CanonicalProduct) -> MatchReason | None:
    text = f"{product.name_fa} {product.description_fa or ''}".lower()
    if candidate.species and _known_term(text, {"dog": "dog", "cat": "cat"}) not in (
        None,
        candidate.species,
    ):
        return MatchReason.SPECIES_MISMATCH
    if candidate.food_type and _known_term(text, {"dry": "dry", "wet": "wet"}) not in (
        None,
        candidate.food_type,
    ):
        return MatchReason.FOOD_TYPE_MISMATCH
    if candidate.veterinary_diet is not None:
        canonical_vet = "veterinary" in text or "vet" in text
        if canonical_vet != candidate.veterinary_diet:
            return MatchReason.VETERINARY_DIET_MISMATCH
    if (
        candidate.declared_total_weight_g
        and product.nominal_quantity_grams
        and candidate.declared_total_weight_g != product.nominal_quantity_grams
    ):
        return MatchReason.PACKAGE_MISMATCH
    return None


def _known_term(text: str, terms: dict[str, str]) -> str | None:
    for needle, value in terms.items():
        if needle in text:
            return value
    return None


def _text_contains(product: CanonicalProduct, value: str | None) -> bool:
    if not value:
        return False
    text = f"{product.name_fa} {product.description_fa or ''}".lower()
    return value.lower() in text
