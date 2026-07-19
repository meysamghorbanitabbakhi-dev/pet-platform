from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Response, status

from app.core.config import Settings, get_settings
from app.core.metrics import metrics
from app.core.redis import ping_redis
from app.db.session import ping_database
from app.integrations.storage.filesystem import LocalFilesystemStorage

router = APIRouter(tags=["health"])
MetricsAuthorization = Annotated[str | None, Header(alias="Authorization")]


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness() -> dict[str, Any]:
    from app.main import get_storage

    checks: dict[str, str] = {}
    failures: list[str] = []
    for name, check in (
        ("database", ping_database),
        ("redis", ping_redis),
        ("storage", get_storage().ensure_ready),
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
    valid = expected is None or secrets.compare_digest(
        authorization or "", f"Bearer {expected}"
    )
    if not valid:
        raise HTTPException(status_code=404, detail="not_found")
    return Response(metrics.render_prometheus(), media_type="text/plain; version=0.0.4")
