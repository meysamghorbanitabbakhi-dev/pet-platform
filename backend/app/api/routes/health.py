from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated, Any

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Header, HTTPException, Response, status
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.core.metrics import metrics
from app.core.redis import ping_redis
from app.db.session import (
    check_app_role_cannot_bypass_rls,
    check_rls_request_context,
    engine,
    ping_app_database,
    ping_database,
)
from app.integrations.storage.filesystem import LocalFilesystemStorage

router = APIRouter(tags=["health"])
MetricsAuthorization = Annotated[str | None, Header(alias="Authorization")]
BACKEND_DIR = Path(__file__).resolve().parents[3]


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


def _expected_alembic_heads() -> list[str]:
    config = AlembicConfig(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return sorted(ScriptDirectory.from_config(config).get_heads())


async def check_migration_head() -> None:
    """Readiness must fail if the running code expects migrations the
    database hasn't applied (or vice versa): a deploy that ships new code
    against a database still on an older revision -- or a rollback that
    reverts code but leaves migrations applied ahead of it -- should never
    be reported as ready."""
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT version_num FROM alembic_version"))
        actual = sorted(row[0] for row in result.all())
    expected = _expected_alembic_heads()
    if actual != expected:
        raise RuntimeError(f"migration head mismatch: database={actual} code={expected}")


@router.get("/health/ready")
async def readiness() -> dict[str, Any]:
    from app.main import get_storage

    checks: dict[str, str] = {}
    failures: list[str] = []
    for name, check in (
        ("database", ping_database),
        ("database_app_role", ping_app_database),
        ("redis", ping_redis),
        ("storage", get_storage().ensure_ready),
        ("migration_head", check_migration_head),
        ("rls_no_bypass", check_app_role_cannot_bypass_rls),
        ("rls_request_context", check_rls_request_context),
    ):
        try:
            await check()
        except Exception:
            checks[name] = "unavailable"
            failures.append(name)
        else:
            checks[name] = "ready"
    if failures:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "checks": checks},
        )
    return {"status": "ready", "checks": checks}


def storage_type_guard(storage: object) -> LocalFilesystemStorage:
    if not isinstance(storage, LocalFilesystemStorage):
        raise RuntimeError("only approved filesystem storage may be active")
    return storage


@router.get("/internal/metrics", include_in_schema=False)
async def prometheus_metrics(authorization: MetricsAuthorization = None) -> Response:
    settings: Settings = get_settings()
    expected = settings.metrics_bearer_token
    valid = expected is None or secrets.compare_digest(authorization or "", f"Bearer {expected}")
    if not valid:
        raise HTTPException(status_code=404, detail="not_found")
    return Response(metrics.render_prometheus(), media_type="text/plain; version=0.0.4")
