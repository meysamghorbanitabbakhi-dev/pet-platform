import pytest
from app.api.pagination import Pagination, page
from pydantic import TypeAdapter, ValidationError


def test_page_reports_stable_cursor_facts() -> None:
    result = page(["a", "b"], total=5, pagination=Pagination(limit=2, offset=2))
    assert result == {
        "items": ["a", "b"],
        "page": {"limit": 2, "offset": 2, "total": 5, "has_more": True},
    }


def test_pagination_contract_rejects_out_of_range_values() -> None:
    adapter = TypeAdapter(Pagination)
    with pytest.raises(ValidationError):
        adapter.validate_python({"limit": 101, "offset": 0})
