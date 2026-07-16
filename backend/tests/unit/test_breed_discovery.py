import pytest
from app.api.routes.pet_health import BreedSelectionBody
from app.modules.pet_knowledge.search import normalize_persian_search, rank_breed_match
from pydantic import ValidationError


def test_persian_search_normalizes_arabic_characters_and_half_space() -> None:
    assert normalize_persian_search("  پودل\u200cمینیاتوری ") == "پودل مینیاتوری"
    assert normalize_persian_search("يكي") == "یکی"


def test_exact_alias_ranks_above_partial_name() -> None:
    match = rank_breed_match(
        "گربه ایرانی",
        name_fa="پرشین",
        name_en="Persian",
        aliases_fa=["گربه ایرانی"],
    )
    assert match == (95, "alias_fa")


def test_unknown_selection_cannot_smuggle_a_breed() -> None:
    with pytest.raises(ValidationError):
        BreedSelectionBody(
            selection_mode="unknown",
            breed_reference_id="dog:poodle",
            identification_source="unknown",
        )


def test_known_selection_requires_explicit_breed() -> None:
    with pytest.raises(ValidationError):
        BreedSelectionBody(selection_mode="known")
