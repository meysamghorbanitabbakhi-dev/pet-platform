from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated

from fastapi import Query


@dataclass(frozen=True, slots=True)
class Pagination:
    limit: Annotated[int, Query(ge=1, le=100)] = 25
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0


def page(items: Sequence[object], *, total: int, pagination: Pagination) -> dict[str, object]:
    return {
        "items": items,
        "page": {
            "limit": pagination.limit,
            "offset": pagination.offset,
            "total": total,
            "has_more": pagination.offset + len(items) < total,
        },
    }
