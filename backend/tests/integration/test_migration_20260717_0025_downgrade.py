from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Coroutine, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import app.db.models  # noqa: F401
import pytest
from alembic import command
from alembic.config import Config
from app.core.config import get_settings
from app.integrations.price_intelligence.service import PriceIntelligenceService
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.skipif(
    os.getenv("K10_RUNTIME_TESTS") != "1",
    reason="K10_RUNTIME_TESTS=1 with PostgreSQL is required",
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
_MATCHES_TABLE = "price_intelligence_external_product_matches"
_REVISION = "20260717_0025"
_DOWN_REVISION = "20260716_0024"


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    # A fresh, self-contained engine is created and disposed inside every
    # call's own asyncio.run() loop (see the helpers below) specifically so
    # nothing here binds to a loop that closes when this function returns --
    # the same failure mode documented on test_price_observation_idempotency
    # .py's dispose fixture, avoided here by never reusing an engine object
    # across two separate _run() calls.
    return asyncio.run(coro)


async def _create_database(admin_url: str, db_name: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        await engine.dispose()


async def _drop_database_and_role(admin_url: str, db_name: str, role_name: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": db_name},
            )
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
            await conn.execute(text(f'DROP ROLE IF EXISTS "{role_name}"'))
    finally:
        await engine.dispose()


@dataclass(slots=True)
class _ScratchEnvironment:
    database_url: str


@pytest.fixture()
def scratch_migration_environment() -> Iterator[_ScratchEnvironment]:
    """A single-purpose, disposable database -- and a matching single-purpose
    RLS app-role name -- for exercising this migration's downgrade fault
    injection, so a failure here can never leave the shared development
    database (which every other test in this suite depends on) in a
    partially-migrated state.

    A prior version of this test ran the same downgrade-then-upgrade cycle
    directly against the shared database. When its recovery `upgrade to
    head` step ever hit a migration still under active development that
    had a real bug (20260721_0045's first draft, before the fix described
    in ADR-006/this program's handoff), alembic's whole-batch transaction
    semantics rolled back to the *start* of that upgrade attempt, leaving
    the shared database many months of migrations behind for every later
    test in the run, with no automatic recovery. This happened twice
    during this program's own development and is the reason this fixture
    exists.

    Isolating by database name alone is not sufficient: 20260720_0040
    (which this test's downgrade path necessarily crosses, since its
    target revision sits below it in the chain) creates, and its
    downgrade later drops, a Postgres ROLE -- cluster-wide, not
    database-scoped. A distinct, per-test role name is therefore also
    required for real isolation; 20260720_0040 reads DATABASE_APP_URL
    fresh from Settings on every alembic invocation (see its own
    docstring), so overriding that env var is enough to redirect it.
    """
    admin_url = make_url(get_settings().database_url)
    token = uuid.uuid4().hex[:12]
    db_name = f"pet_platform_migration_test_{token}"
    role_name = f"pet_platform_app_test_{token}"

    admin_url_str = admin_url.render_as_string(hide_password=False)
    _run(_create_database(admin_url_str, db_name))

    scratch_database_url = admin_url.set(database=db_name).render_as_string(hide_password=False)
    scratch_app_url = admin_url.set(
        database=db_name, username=role_name, password=role_name
    ).render_as_string(hide_password=False)

    original_database_url = os.environ.get("DATABASE_URL")
    original_app_url = os.environ.get("DATABASE_APP_URL")
    os.environ["DATABASE_URL"] = scratch_database_url
    os.environ["DATABASE_APP_URL"] = scratch_app_url
    get_settings.cache_clear()
    try:
        yield _ScratchEnvironment(database_url=scratch_database_url)
    finally:
        if original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_database_url
        if original_app_url is None:
            os.environ.pop("DATABASE_APP_URL", None)
        else:
            os.environ["DATABASE_APP_URL"] = original_app_url
        get_settings.cache_clear()
        _run(_drop_database_and_role(admin_url_str, db_name, role_name))


async def _seed_unmatched_row(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            service = PriceIntelligenceService(session)
            token = uuid.uuid4().hex
            source = await service.get_or_create_source(
                f"downgrade-test-{token}",
                name="Downgrade test source",
                base_url="https://example.test",
                country_code="AM",
                default_currency="AMD",
            )
            seller = await service.get_or_create_seller(source.id, seller_name=f"seller-{token}")
            product, _ = await service.upsert_external_product(
                source.id,
                f"product-{token}",
                source_url=f"https://example.test/{token}",
                source_title=f"Unmatched downgrade-test food {token}",
                brand_name=f"Nonexistent downgrade-test brand {token}",
                seller_id=seller.id,
            )
            result = await service.run_match_for_product(product)
            assert result.method.value == "unmatched", (
                "test setup assumes a fresh, unrecognizable product does not match any "
                "canonical product; got a real match instead, which would invalidate this test"
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _count_unmatched_rows(database_url: str) -> int:
    engine = create_async_engine(database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            result = await session.execute(
                text(f"SELECT COUNT(*) FROM {_MATCHES_TABLE} WHERE match_method = 'unmatched'")
            )
            return int(result.scalar_one())
    finally:
        await engine.dispose()


async def _delete_unmatched_rows(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await session.execute(
                text(f"DELETE FROM {_MATCHES_TABLE} WHERE match_method = 'unmatched'")
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _current_alembic_version(database_url: str) -> str:
    engine = create_async_engine(database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            result = await session.execute(text("SELECT version_num FROM alembic_version"))
            return str(result.scalar_one())
    finally:
        await engine.dispose()


def test_downgrade_fails_closed_with_unmatched_rows_then_succeeds_after_cleanup(
    scratch_migration_environment: _ScratchEnvironment,
) -> None:
    database_url = scratch_migration_environment.database_url
    config = _alembic_config()
    # Builds the schema from empty, exercising the entire migration chain
    # (not just the tail this test cares about) against a database no other
    # test can see -- a strictly more thorough check than the shared-database
    # version this replaces, which assumed the shared database was already
    # at head rather than proving the chain applies cleanly from scratch.
    command.upgrade(config, "head")
    original_head = _run(_current_alembic_version(database_url))
    try:
        _run(_seed_unmatched_row(database_url))
        assert _run(_count_unmatched_rows(database_url)) >= 1

        with pytest.raises(RuntimeError, match=_REVISION):
            command.downgrade(config, _DOWN_REVISION)

        # The controlled failure must abort the whole downgrade batch, not
        # leave it partially applied -- alembic runs the full requested
        # range in one transaction by default, so a failure anywhere in it
        # must roll back to the version we started from.
        assert _run(_current_alembic_version(database_url)) == original_head

        _run(_delete_unmatched_rows(database_url))
        command.downgrade(config, _DOWN_REVISION)
        assert _run(_current_alembic_version(database_url)) == _DOWN_REVISION
    finally:
        command.upgrade(config, "head")
