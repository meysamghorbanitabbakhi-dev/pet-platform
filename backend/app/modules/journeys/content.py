from __future__ import annotations

from datetime import datetime
from typing import Any


def content_str(content: dict[str, object], key: str) -> str | None:
    value = content.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def content_int(content: dict[str, object], key: str) -> int | None:
    value = content.get(key)
    return value if isinstance(value, int) and value > 0 else None


def content_steps(content: dict[str, object]) -> list[dict[str, Any]]:
    value = content.get("steps")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def parse_content_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def valid_journey_content(content: dict[str, object]) -> bool:
    if not content_str(content, "professional_approval_ref"):
        return False
    if not content_str(content, "garden_object_key"):
        return False
    active_from = parse_content_datetime(content.get("active_from"))
    active_until = parse_content_datetime(content.get("active_until"))
    if content.get("active_from") is not None and active_from is None:
        return False
    if content.get("active_until") is not None and active_until is None:
        return False
    if active_from is not None and active_until is not None and active_from >= active_until:
        return False
    eligible_species = content.get("eligible_species")
    if eligible_species is not None and (
        not isinstance(eligible_species, list)
        or not eligible_species
        or any(item not in ("dog", "cat") for item in eligible_species)
    ):
        return False
    steps = content_steps(content)
    if not steps:
        return False
    step_keys: set[str] = set()
    answer_pairs: set[tuple[str, str]] = set()
    for step in steps:
        key = content_str(step, "key")
        if key is None or key in step_keys:
            return False
        if content_str(step, "title_fa") is None or content_str(step, "body_fa") is None:
            return False
        step_keys.add(key)
        answers = step.get("allowed_answers")
        if not isinstance(answers, list) or not answers:
            return False
        answer_keys: set[str] = set()
        for answer in answers:
            if not isinstance(answer, dict):
                return False
            answer_key = content_str(answer, "key")
            if answer_key is None or answer_key in answer_keys:
                return False
            if content_str(answer, "label_fa") is None:
                return False
            answer_keys.add(answer_key)
            answer_pairs.add((key, answer_key))
    required = content.get("completion_requires")
    if not isinstance(required, list) or not required:
        return False
    required_keys = {item for item in required if isinstance(item, str)}
    return len(required_keys) == len(required) and required_keys <= step_keys and bool(answer_pairs)


def journey_deliverable(content: dict[str, object], species: str | None, now: datetime) -> bool:
    if not valid_journey_content(content):
        return False
    active_from = parse_content_datetime(content.get("active_from"))
    active_until = parse_content_datetime(content.get("active_until"))
    if active_from is not None and now < active_from:
        return False
    if active_until is not None and now >= active_until:
        return False
    eligible_species = content.get("eligible_species")
    if (
        species is not None
        and isinstance(eligible_species, list)
        and species not in eligible_species
    ):
        return False
    return True


def valid_check_in(content: dict[str, object], check_in_key: str, answer_key: str) -> bool:
    for step in content_steps(content):
        if step.get("key") != check_in_key:
            continue
        answers = step.get("allowed_answers")
        if not isinstance(answers, list):
            return False
        return any(
            isinstance(answer, dict) and answer.get("key") == answer_key for answer in answers
        )
    return False


def completion_requirements_met(content: dict[str, object], submitted_keys: set[str]) -> bool:
    required = content.get("completion_requires")
    if not isinstance(required, list):
        return False
    required_keys = {str(item) for item in required if isinstance(item, str)}
    return bool(required_keys) and required_keys.issubset(submitted_keys)
