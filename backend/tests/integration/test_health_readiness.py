from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from app.api.routes.health import _expected_alembic_heads, check_migration_head
from app.db.session import (
    _assert_request_context_round_trip,
    _assert_role_is_not_privileged,
    check_app_role_cannot_bypass_rls,
    check_rls_request_context,
    close_database,
    ping_app_database,
)
from app.main import create_app
from fastapi import FastAPI

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL is required",
)


@pytest.fixture(autouse=True)
async def dispose_engine_between_event_loops() -> AsyncIterator[None]:
    yield
    await close_database()


async def test_ping_app_database_succeeds_against_real_app_role() -> None:
    await ping_app_database()


async def test_check_app_role_cannot_bypass_rls_passes_for_the_real_app_role() -> None:
    await check_app_role_cannot_bypass_rls()


@pytest.mark.parametrize(
    ("rolsuper", "rolbypassrls"),
    [(True, False), (False, True), (True, True)],
)
def test_assert_role_is_not_privileged_rejects_any_privileged_combination(
    rolsuper: bool, rolbypassrls: bool
) -> None:
    """The real-role integration test above only proves today's environment
    is configured correctly; this proves the guard itself would actually
    catch a future misconfiguration (a connection string accidentally
    pointed at a superuser or BYPASSRLS role) rather than passing no
    matter what it's given."""
    with pytest.raises(RuntimeError, match="bypass row-level security"):
        _assert_role_is_not_privileged(rolsuper, rolbypassrls)


def test_assert_role_is_not_privileged_accepts_an_unprivileged_role() -> None:
    _assert_role_is_not_privileged(False, False)


async def test_check_rls_request_context_round_trips_against_real_postgres() -> None:
    await check_rls_request_context()


def test_assert_request_context_round_trip_rejects_operator_mismatch() -> None:
    identity = uuid.uuid4()
    household = uuid.uuid4()
    with pytest.raises(RuntimeError, match="app_is_operator"):
        _assert_request_context_round_trip(True, identity, [household], identity, household)


def test_assert_request_context_round_trip_rejects_identity_mismatch() -> None:
    household = uuid.uuid4()
    with pytest.raises(RuntimeError, match="app_identity_id"):
        _assert_request_context_round_trip(
            False, uuid.uuid4(), [household], uuid.uuid4(), household
        )


def test_assert_request_context_round_trip_rejects_household_mismatch() -> None:
    identity = uuid.uuid4()
    with pytest.raises(RuntimeError, match="app_household_ids"):
        _assert_request_context_round_trip(
            False, identity, [uuid.uuid4()], identity, uuid.uuid4()
        )


def test_assert_request_context_round_trip_accepts_a_matching_readback() -> None:
    identity = uuid.uuid4()
    household = uuid.uuid4()
    _assert_request_context_round_trip(False, identity, [household], identity, household)


async def test_check_migration_head_passes_when_database_is_at_the_code_head() -> None:
    await check_migration_head()


async def test_check_migration_head_detects_a_database_behind_the_code_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reproduces exactly the scenario Section 10.4 calls out: code that
    expects a migration the database hasn't applied yet. Rather than
    actually desyncing the shared test database (which every other test
    in this run relies on being at head), this patches what the check
    believes the code's expected head to be -- proving the comparison
    itself, not just that a real head happens to match today."""
    monkeypatch.setattr(
        "app.api.routes.health._expected_alembic_heads",
        lambda: ["not_a_real_revision"],
    )
    with pytest.raises(RuntimeError, match="migration head mismatch"):
        await check_migration_head()


def test_expected_alembic_heads_returns_exactly_one_head() -> None:
    """A second, independent head would mean an unmerged migration branch
    -- this readiness check's comparison is only meaningful if the code
    side of it is unambiguous."""
    heads = _expected_alembic_heads()
    assert len(heads) == 1


@pytest.fixture()
async def app_and_client() -> AsyncIterator[tuple[FastAPI, httpx.AsyncClient]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield app, client
    app.dependency_overrides.clear()


async def test_readiness_endpoint_reports_ready_with_all_expected_checks(
    app_and_client: tuple[FastAPI, httpx.AsyncClient],
) -> None:
    _, client = app_and_client
    response = await client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"] == {
        "database": "ready",
        "database_app_role": "ready",
        "redis": "ready",
        "storage": "ready",
        "migration_head": "ready",
        "rls_no_bypass": "ready",
        "rls_request_context": "ready",
    }
