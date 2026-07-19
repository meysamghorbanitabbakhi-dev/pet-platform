from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from app.api.errors import http_exception_handler, validation_exception_handler
from app.api.middleware import ProductionGuardMiddleware, RequestIdMiddleware
from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.redis import close_redis
from app.db.session import close_database
from app.integrations.storage.filesystem import LocalFilesystemStorage


@lru_cache
def get_storage() -> LocalFilesystemStorage:
    settings = get_settings()
    return LocalFilesystemStorage(settings.media_root)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await get_storage().ensure_ready()
    yield
    await close_redis()
    await close_database()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    application = FastAPI(
        title="Pet Platform Backend",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
    )
    application.add_middleware(
        ProductionGuardMiddleware,
        max_body_bytes=settings.max_request_body_bytes,
        hsts_enabled=settings.security_hsts_enabled,
    )
    application.add_middleware(RequestIdMiddleware)
    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.include_router(health_router)
    application.include_router(api_router, prefix=settings.api_prefix)
    return application


app = create_app()
