from __future__ import annotations

import re
import unicodedata

_ARABIC_TO_PERSIAN = str.maketrans({"ي": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه"})


def normalize_persian_search(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).translate(_ARABIC_TO_PERSIAN)
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("M")
    )
    normalized = normalized.replace("\u200c", " ").casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def rank_breed_match(
    query: str, *, name_fa: str, name_en: str, aliases_fa: list[str]
) -> tuple[int, str] | None:
    needle = normalize_persian_search(query)
    if not needle:
        return None
    candidates = [("name_fa", name_fa), *[("alias_fa", alias) for alias in aliases_fa]]
    candidates.append(("name_en", name_en))
    best: tuple[int, str] | None = None
    for field, value in candidates:
        candidate = normalize_persian_search(value)
        if candidate == needle:
            score = 100 if field == "name_fa" else 95 if field == "alias_fa" else 90
        elif candidate.startswith(needle):
            score = 80 if field == "name_fa" else 75 if field == "alias_fa" else 70
        elif needle in candidate:
            score = 60 if field == "name_fa" else 55 if field == "alias_fa" else 50
        else:
            continue
        result = (score, field)
        if best is None or result[0] > best[0]:
            best = result
    return best
