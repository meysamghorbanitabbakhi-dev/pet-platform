from __future__ import annotations

import re
import time
from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core.metrics import metrics

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if _SAFE_REQUEST_ID.fullmatch(supplied) else str(uuid4())
        token = request_id_context.set(request_id)
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        finally:
            request_id_context.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response


class ProductionGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, max_body_bytes: int, hsts_enabled: bool) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.max_body_bytes = max_body_bytes
        self.hsts_enabled = hsts_enabled

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.monotonic()
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                too_large = int(content_length) > self.max_body_bytes
            except ValueError:
                return self._secure(self._error(request, 400, "invalid_content_length"))
            if too_large:
                return self._secure(self._error(request, 413, "request_body_too_large"))
        response = await call_next(request)
        response = self._secure(response)
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
        metrics.observe(request.method, route_path, response.status_code, elapsed_ms)
        return response

    def _secure(self, response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        if self.hsts_enabled:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @staticmethod
    def _error(request: Request, status_code: int, code: str) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code,
                    "message": code.replace("_", " "),
                    "details": None,
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )
